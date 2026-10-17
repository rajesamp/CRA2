"""Task 15: explicit LangGraph host; MCP tools remain a guarded boundary.

No durable graph checkpoints, memory writes, autonomous tool loop or raw-state
streaming. Week 1's retrieval/provider/policy adapters retain their behavior.
"""

import re
import unicodedata
from pathlib import Path
from string import Formatter
from typing import TypedDict
from uuid import uuid4

import anyio
from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context

from cra2 import system2
from cra2.advisor import ADVISORY, CATALOG
from week1 import chat, provider, responses, routing
from week2.contracts import ContractError, NAMES, checked, decode_json, validate_result
from week2.mcp_client import call_tools

COPY = Path(__file__).with_name("responses.json")
PARAMETERS = {
    "snapshot": set(), "tool_failure": set(), "retrieval_failure": set(),
    "unavailable": set(),
    "health": {"service", "health", "freeze", "evidence"},
    "graph": {"service", "dependencies", "all_dependencies", "dependents",
              "all_dependents", "evidence"},
}


def load_copy():
    with COPY.open(encoding="utf-8") as stream:
        raw = stream.read(16385)
    if len(raw) > 16384:
        raise ValueError("Invalid Week 2 response catalog")
    data = decode_json(raw)
    checked(data, "invalid_catalog")
    if not isinstance(data, dict) or set(data) != set(PARAMETERS):
        raise ValueError("Invalid Week 2 response catalog")
    for key, text in data.items():
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Invalid Week 2 response catalog")
        fields = set()
        for _, field, spec, conversion in Formatter().parse(text):
            if field is not None:
                if spec or conversion or field not in PARAMETERS[key]:
                    raise ValueError("Invalid Week 2 response catalog")
                fields.add(field)
        if fields != PARAMETERS[key]:
            raise ValueError("Invalid Week 2 response catalog")
    return data


class State(TypedDict, total=False):
    question: str
    history: list
    mode: str
    service: str
    route: str
    calls: list
    hits: list
    answer: str
    trace: dict
    tools: dict


def _answer(text, status):
    return {"answer": text + "\n\n" + ADVISORY,
            "trace": {"status": status, "retrieved": [],
                      "provider_used": False, "request_attempted": False},
            "route": "done"}


def _context_service(question, history):
    names = chat._services(question)
    if names:
        return names[0] if len(names) == 1 else None
    # Unknown explicit names never inherit a previously discussed service.
    if re.search(r"\b[a-z0-9-]+-(?:service|gateway|api)\b", question.lower()):
        return None
    if not re.search(r"\b(?:this|that|same|it)\b", question.lower()):
        return None
    for message in reversed(history[-6:]):
        if isinstance(message, dict) and message.get("role") == "user":
            content = message.get("content")
            if isinstance(content, list):
                content = "\n".join(p.get("text", "") for p in content
                                    if isinstance(p, dict) and isinstance(p.get("text"), str))
            if isinstance(content, str):
                return chat._service(content[:chat.MAX_QUESTION])
    return None


def build_workflow(*, retriever=None, reviewer=None, tool_runner=None, index_path=chat.INDEX):
    """Dependencies are runtime collaborators, never serialized graph state."""
    retrieve = retriever or chat.search
    review = reviewer or provider.assess
    run_tools = tool_runner or call_tools
    copy = load_copy()
    catalog = responses.load()

    def classify(state):
        question, mode, history = state["question"], state["mode"], state["history"]
        if not isinstance(question, str) or not question.strip() or len(question) > chat.MAX_QUESTION:
            return _answer(responses.message(catalog, "input_length"), "needs_clarification")
        if any(unicodedata.category(c).startswith("C") and c not in "\n\r\t" for c in question):
            return _answer(responses.message(catalog, "control_characters"), "needs_clarification")
        if mode not in {"Local evidence only", "Groq assessment"}:
            return _answer(responses.message(catalog, "invalid_mode"), "needs_clarification")
        decision = routing.task(question, catalog)
        active = routing.active_request(question)
        scope = routing.classify_scope(question, decision, CATALOG)
        if scope == "non_cra2" or decision is not None:
            return {"route": "legacy"}
        if re.search(r"\b(?:approve|authorize|merge|deploy|block)\b", active):
            return _answer(responses.message(catalog, "advisory_boundary"), "advisory_boundary")
        if re.search(r"\bremember\b|\b(?:save|store)\b.*\bpreference", active):
            return _answer(responses.message(catalog, "memory_deferred"), "deferred")
        names = chat._services(question)
        if len(names) > 1:
            return _answer(responses.message(catalog, "multiple_services"), "needs_clarification")
        service = _context_service(question, history)
        if not service:
            return _answer(responses.message(catalog, "missing_service"), "needs_clarification")
        specific = chat._specific_change(question, service)
        dependency = bool(re.search(r"\bdepend(?:s|ents|encies)?\b", active))
        health = bool(re.search(r"\b(?:health|status|freeze)\b", active))
        history_only = bool(re.search(
            r"\b(?:had|caused|similar|past|previous)\b.*\bincidents?\b|\bincidents?\b.*\b(?:before|history|past)\b",
            active))
        if history_only and not (health or dependency):
            return {"route": "legacy"}
        if not specific and not (health or dependency):
            return _answer(responses.message(catalog, "specific_change", service=service), "needs_clarification")
        selected = NAMES if specific else tuple(
            name for name, needed in zip(NAMES, (health, dependency)) if needed)
        return {"route": "retrieve" if specific else "tools", "service": service,
                "calls": [(name, {"service_name": service}) for name in selected]}

    def legacy(state):
        answer, trace = chat.respond(state["question"], state["history"], state["mode"],
                                     index_path=index_path, retriever=retrieve, reviewer=review)
        return {"answer": answer, "trace": trace}

    def retrieval(state):
        try:
            hits = retrieve(state["question"], index_path, limit=3, service=state["service"])
            checked(hits, "invalid_evidence")
            return {"hits": hits, "route": "tools"}
        except Exception:
            return _answer(copy["retrieval_failure"], "retrieval_unavailable")

    async def tools_node(state):
        bundle = await run_tools(state["calls"])
        checked(bundle, "invalid_result")
        if bundle["status"] == "ok":
            expected = {name for name, _ in state["calls"]}
            if set(bundle["outputs"]) != expected:
                raise ContractError("invalid_result")
            for name, arguments in state["calls"]:
                validate_result(name, arguments["service_name"], bundle["outputs"][name])
        return {"tools": bundle}

    def compose(state):
        bundle = state["tools"]
        outputs = bundle["outputs"]
        if bundle["status"] != "ok" or any(r["status"] != "ok" for r in outputs.values()):
            result = _answer(copy["tool_failure"], "tools_unavailable")
            result["trace"]["events"] = bundle["events"]
            return result
        if "hits" in state:
            tool_citations = set()
            def enriched_review(payload, weights):
                historical_keys = set(payload["evidence_keys"])
                payload = dict(payload)
                payload["tool_results"] = outputs
                payload["evidence_keys"] = sorted(set(payload["evidence_keys"]) | {
                    key for result in outputs.values() for key in result["evidence"]})
                payload["source_scope"] = (
                    "Historical corpus and actual MCP calls to synthetic snapshots. "
                    "Observation time, freshness and active incidents are unknown; "
                    "freeze applicability is unconfirmed. Configured team policy wins."
                )
                responses.guard(payload)
                result = review(payload, weights)
                responses.guard(result)
                # The unchanged Week 1 adapter owns historical-citation checks.
                # Validate combined citations here, then project the historical
                # subset into that adapter and retain tool citations in trace.
                accepted = []
                allowed = set(payload["evidence_keys"])
                tool_keys = allowed - historical_keys
                for comment in result["out"]["comments"]:
                    if (set(comment["evidence"]) & {h["chunk_id"] for h in state["hits"]}
                            and system2._comment_allowed(comment, allowed)):
                        tool_citations.update(set(comment["evidence"]) & tool_keys)
                        accepted.append(dict(comment, evidence=[k for k in comment["evidence"] if k in historical_keys]))
                return dict(result, out=dict(result["out"], comments=accepted))

            answer, trace = chat.respond(
                state["question"], state["history"], state["mode"], index_path=index_path,
                retriever=lambda *_a, **_k: state["hits"], reviewer=enriched_review,
            )
            trace["assessment_tool_citations"] = sorted(tool_citations)
        else:
            answer = ADVISORY
            trace = {"status": "tool_evidence", "retrieved": [],
                     "provider_used": False, "request_attempted": False}
        sections = [copy["snapshot"]]
        if NAMES[0] in outputs:
            health = outputs[NAMES[0]]
            sections.append(copy["health"].format(
                service=state["service"], health=health["health"],
                freeze=health["freeze_window"]["status"], evidence=", ".join(health["evidence"])))
        if NAMES[1] in outputs:
            graph = outputs[NAMES[1]]
            sections.append(copy["graph"].format(
                service=state["service"],
                dependencies=", ".join(graph["dependencies"]["direct"]) or "[]",
                all_dependencies=", ".join(graph["dependencies"]["transitive"]) or "[]",
                dependents=", ".join(graph["dependents"]["direct"]) or "[]",
                all_dependents=", ".join(graph["dependents"]["transitive"]) or "[]",
                evidence=", ".join(graph["evidence"])))
        answer = answer.removesuffix(ADVISORY).rstrip() + "\n\n" + "\n\n".join(sections) + "\n\n" + ADVISORY
        trace.update(events=bundle["events"], source_scope="Historical evidence and MCP synthetic snapshots; current state unverified")
        return {"answer": answer.strip(), "trace": trace}

    def output_guard(state):
        responses.guard([state["answer"], state["trace"]])
        return {}

    builder = StateGraph(State)
    for name, node in (("classify", classify), ("legacy", legacy), ("retrieve", retrieval),
                       ("tools", tools_node), ("compose", compose), ("output_guard", output_guard)):
        builder.add_node(name, node)
    builder.add_edge(START, "classify")
    builder.add_conditional_edges("classify", lambda s: s["route"],
                                  {"done": "output_guard", "legacy": "legacy", "retrieve": "retrieve", "tools": "tools"})
    builder.add_conditional_edges("retrieve", lambda s: s["route"],
                                  {"done": "output_guard", "tools": "tools"})
    builder.add_edge("legacy", "output_guard")
    builder.add_edge("tools", "compose")
    builder.add_edge("compose", "output_guard")
    builder.add_edge("output_guard", END)
    return builder.compile()


async def arespond(question, history=None, mode="Local evidence only", **collaborators):
    """Only final guarded answer and trace leave this boundary; no raw state."""
    request_id = uuid4().hex
    try:
        responses.guard([question, history, mode])
        if history is not None and (not isinstance(history, list) or len(history) > 100):
            raise ValueError("Invalid history")
        graph = build_workflow(**collaborators)
        # Environment-enabled LangSmith tracing must not upload raw state.
        with tracing_context(enabled=False):
            result = await graph.ainvoke({"question": question, "history": history or [], "mode": mode},
                                        config={"recursion_limit": 10, "callbacks": []})
        trace = result["trace"]
        trace.setdefault("provider_used", False)
        trace.setdefault("request_attempted", False)
        trace.update(request_id=request_id, orchestration="langgraph", memory="not_implemented")
        responses.guard([result["answer"], trace])
        return result["answer"], trace
    except Exception:
        # Failure text is deliberately static even if a catalog/graph is corrupt.
        return ("The request could not be processed. No risk indication is assigned. "
                "This is advisory only; a human decision is required.",
                {"status": "unavailable", "request_id": request_id, "retrieved": [],
                 "provider_used": False, "request_attempted": False})


def respond(question, history=None, mode="Local evidence only", **collaborators):
    return anyio.run(lambda: arespond(question, history, mode, **collaborators))
