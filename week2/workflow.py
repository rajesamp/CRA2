"""Task 15: explicit LangGraph host; MCP tools remain a guarded boundary.

Explicit team-preference memory is separate from ephemeral graph state. No
durable conversation checkpoints, autonomous loop, or raw-state streaming.
"""

import re
import html
import unicodedata
import inspect
from datetime import datetime, timezone
from time import perf_counter
from pathlib import Path
from string import Formatter
from typing import TypedDict
from uuid import uuid4

import anyio
from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context

from cra2 import system2
from cra2 import config
from cra2.team_settings import load_settings
from cra2.advisor import ADVISORY, CATALOG
from week1 import chat, provider, responses, routing
from week2.contracts import ContractError, NAMES, checked, decode_json, validate_result
from week2.mcp_client import call_tools
from week2.memory import MemoryStore, MemoryUnavailable
from week2.preferences import parse_command, effective_policy
from week2.help import capability_lines, help_answer, help_topic
from week3.guardrails import LocalRails, RailUnavailable
from week3.support import coverage, approval_request, advisory_question
from week3.cache import identity, CacheToolError
from week4.telemetry import TelemetryUnavailable, TRANSPORTS
from week4.langsmith_tracing import EXPORTER, credentials as tracing_credentials
from cra2.secrets import reject_credentials

COPY = Path(__file__).with_name("responses.json")
HOST_TEAM = chat.TEAM_SETTINGS["team"]
PARAMETERS = {
    "snapshot": set(), "tool_failure": set(), "retrieval_failure": set(),
    "unavailable": set(),
    "memory_saved": {"service"}, "memory_help": set(), "memory_unavailable": set(),
    "memory_flag": {"service", "flag", "effective", "source"},
    "memory_note": {"note"}, "memory_conflict": set(),
    "health": {"service", "health", "freeze", "evidence"},
    "graph": {"service", "dependencies", "all_dependencies", "dependents",
              "all_dependents", "evidence"},
    "chat_assessed": {"level"}, "chat_evidence_only": set(),
    "chat_provider_unavailable": set(), "chat_insufficient_evidence": set(),
    "chat_retrieval_unavailable": set(), "chat_tools_unavailable": set(),
    "chat_memory_saved": set(), "chat_memory_unavailable": set(),
    "chat_unavailable": set(),
    "chat_timeout_change": {"direction", "percent"}, "chat_timeout_checks": set(),
    "chat_retry_change": {"before", "after"}, "chat_retry_checks": set(),
    "chat_change_checks": set(), "chat_review_checks": {"checks"},
    "chat_specific_change": {"service"},
    "help_overview": set(), "help_capabilities": set(), "help_services": {"services"},
    "help_examples": {"service"}, "help_modes": set(), "help_memory": set(),
    "help_trace": set(), "help_limits": set(), "help_tools": set(),
    "help_preference_commands": {"service"},
    "help_security": set(),
    "guardrail_failure": set(), "guardrail_blocked": set(),
    "approval_continuation": set(), "unsupported_mechanism": set(),
    "stale_context": set(),
    "telemetry_failure": set(),
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
    memory_record: dict
    policy: dict
    next_route: str
    memory_updates: dict


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


def build_workflow(*, retriever=None, reviewer=None, tool_runner=None, index_path=chat.INDEX, memory_store=None, guardrails=None, caches=None, spans=None):
    """Dependencies are runtime collaborators, never serialized graph state."""
    retrieve = retriever or chat.search
    review = reviewer or provider.assess
    run_tools = tool_runner or call_tools
    copy = load_copy()
    catalog = responses.load()
    store = MemoryStore() if memory_store is None else memory_store
    rails = LocalRails() if guardrails is None else guardrails
    cache_events = []
    spans = [] if spans is None else spans

    def timed(name,node):
        async def wrapped(state):
            began=perf_counter();outcome="error"
            started_at = datetime.now(timezone.utc).isoformat()
            try:
                result=node(state)
                if inspect.isawaitable(result):result=await result
                outcome="completed"
                return result
            finally:
                spans.append({"stage":name,"outcome":outcome,"duration_ms":round((perf_counter()-began)*1000,3),
                              "started_at":started_at,"ended_at":datetime.now(timezone.utc).isoformat()})
        return wrapped

    def policy_settings():
        settings=load_settings(config.DATA_DIR,CATALOG)
        if settings["team"]!=HOST_TEAM:
            raise MemoryUnavailable("host_identity_changed")
        return settings

    def current_policy(service, record):
        return effective_policy(service, record, team_settings=policy_settings())

    def cache_scope(state):
        host_store = getattr(store, "store", store)
        return identity([getattr(host_store,"team",None),str(getattr(host_store,"path",id(host_store))),
            state.get("memory_record"), state.get("policy")])

    def get_hits(state, query, path, **options):
        from week1.retrieval import search
        if caches is not None and retrieve is search:
            return caches.retrieve(query,path,scope=cache_scope(state),events=cache_events,**options)
        return retrieve(query,path,**options)

    async def rail_check(stage, payload):
        started_at = datetime.now(timezone.utc).isoformat()
        try:
            if not await rails.check(stage, payload):
                return _answer(copy["guardrail_blocked"], "guardrail_blocked")
        except Exception:
            return _answer(copy["guardrail_failure"], "guardrails_unavailable")
        finally:
            if rails.events and rails.events[-1].get("stage") == stage:
                rails.events[-1].update(started_at=started_at, ended_at=datetime.now(timezone.utc).isoformat())
        return None

    async def classify(state):
        question, mode, history = state["question"], state["mode"], state["history"]
        if not isinstance(question, str) or not question.strip() or len(question) > chat.MAX_QUESTION:
            return _answer(responses.message(catalog, "input_length"), "needs_clarification")
        if any(unicodedata.category(c).startswith("C") and c not in "\n\r\t" for c in question):
            return _answer(responses.message(catalog, "control_characters"), "needs_clarification")
        if mode not in {"Local evidence only", "Groq assessment"}:
            return _answer(responses.message(catalog, "invalid_mode"), "needs_clarification")
        refused = await rail_check("input", question)
        if refused:
            return refused
        decision = routing.task(question, dict(catalog, capabilities=capability_lines(copy)))
        active = routing.active_request(question)
        if decision and decision["kind"] == "clarify":
            return _answer(decision["question"], "needs_clarification")
        if (decision and decision["kind"] == "help" and chat._services(question)
                and re.search(r"\b(?:assess|evaluate|review)\b", active)):
            return _answer(responses.message(catalog, "help_or_change"), "needs_clarification")
        topic = help_topic(question, decision, CATALOG)
        if topic:
            result = _answer(help_answer(topic, copy, CATALOG, decision), "help")
            result["trace"]["topic"] = topic
            return result
        scope = routing.classify_scope(question, decision, CATALOG)
        if scope == "non_cra2" or decision is not None:
            return {"route": "legacy"}
        # An anchored preference command stores its bounded note as inert data;
        # words inside that note are never interpreted as execution requests.
        command = parse_command(question)
        if command:
            return {"route": "memory_write", "service": command["service"], "memory_updates": command["updates"]}
        if approval_request(question):
            return _answer(responses.message(catalog, "advisory_boundary"), "advisory_boundary")
        if re.search(r"\bremember\b|\b(?:save|store)\b.*\bpreference", active):
            return _answer(copy["memory_help"], "needs_clarification")
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
            return {"route": "memory_read", "service": service, "next_route": "legacy"}
        if not specific and not (health or dependency):
            return _answer(copy["chat_specific_change"].format(service=service), "needs_clarification")
        selected = NAMES if specific else tuple(
            name for name, needed in zip(NAMES, (health, dependency)) if needed)
        return {"route": "memory_read", "next_route": "retrieve" if specific else "tools", "service": service,
                "calls": [(name, {"service_name": service}) for name in selected]}

    def memory_read(state):
        try:
            settings=policy_settings()
            record = store.read(state["service"])
            policy = effective_policy(state["service"], record,team_settings=settings)
            responses.guard([record, policy])
            return {"memory_record": record, "policy": policy, "route": state["next_route"]}
        except (MemoryUnavailable, ValueError, OSError):
            result = _answer(copy["memory_unavailable"], "memory_unavailable")
            result["trace"]["memory"] = {"status": "unavailable"}
            return result

    def memory_write(state):
        try:
            policy_settings()
            record = store.write(state["service"], **state["memory_updates"])
            result = _answer(copy["memory_saved"].format(service=state["service"]), "memory_saved")
            result.update(memory_record=record, policy=current_policy(state["service"], record))
            result["trace"]["events"] = [{"event": "memory_written", "service": state["service"]}]
            return result
        except (MemoryUnavailable, ValueError, OSError):
            result = _answer(copy["memory_unavailable"], "memory_unavailable")
            result["trace"]["memory"] = {"status": "unavailable"}
            return result

    async def legacy(state):
        answer, trace = chat.respond(state["question"], state["history"], state["mode"],
                                     index_path=index_path, retriever=lambda q,p,**k:get_hits(state,q,p,**k), reviewer=review)
        if trace.get("retrieved"):
            refused = await rail_check("context", trace["retrieved"])
            if refused:
                return refused
        return {"answer": answer, "trace": trace}

    async def retrieval(state):
        try:
            hits = get_hits(state, state["question"], index_path, limit=3, service=state["service"])
            checked(hits, "invalid_evidence")
            refused = await rail_check("context", hits)
            if refused:
                return refused
            return {"hits": hits, "route": "tools"}
        except Exception:
            return _answer(copy["retrieval_failure"], "retrieval_unavailable")

    async def tools_node(state):
        try:
            if caches is not None and tool_runner is None:
                bundle = await caches.call_tools(state["calls"],scope=cache_scope(state),runner=run_tools)
                cache_events.extend(bundle.pop("cache_events"))
            else:
                bundle = await run_tools(state["calls"])
        except CacheToolError as error:
            bundle = error.bundle
        except Exception:
            bundle = {"status":"error","outputs":{},"events":[{"event":"mcp_failed","code":"cache_or_source_unavailable"}],
                "metrics":{"status":"unavailable","attempted":None,"failed":None}}
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
            result["trace"]["mcp"] = bundle.get("metrics", {"status":"unavailable","attempted":None,"failed":None})
            return result
        if "hits" in state:
            support = coverage(state["question"], state["hits"])
            unsupported = support["status"] == "unsupported"
            tool_citations = set()
            accepted_reviews = []
            def enriched_review(payload, weights):
                historical_keys = set(payload["evidence_keys"])
                payload = dict(payload)
                payload["tool_results"] = outputs
                payload["settings"] = state["policy"]
                payload["settings_conflicts"] = state["policy"]["conflicts"]
                payload["evidence_keys"] = sorted(set(payload["evidence_keys"]) | {
                    key for result in outputs.values() for key in result["evidence"]} |
                    set(state["policy"]["sources"].values()))
                payload["source_scope"] = (
                    "Historical corpus and actual MCP calls to synthetic snapshots. "
                    "Observation time, freshness and active incidents are unknown; "
                    "freeze applicability is unconfirmed. Configured team policy wins."
                )
                responses.guard(payload)
                began = perf_counter()
                started_at = datetime.now(timezone.utc).isoformat()
                try:
                    result = review(payload, weights)
                finally:
                    spans.append({"stage":"reviewer","outcome":"invoked_provider_adapter" if reviewer is None else "invoked_offline_adapter",
                        "duration_ms":round((perf_counter()-began)*1000,3),
                        "started_at":started_at,"ended_at":datetime.now(timezone.utc).isoformat()})
                responses.guard(result)
                # The unchanged Week 1 adapter owns historical-citation checks.
                # Validate combined citations here, then project the historical
                # subset into that adapter and retain tool citations in trace.
                accepted = []
                allowed = set(payload["evidence_keys"])
                tool_keys = {key for output in outputs.values() for key in output["evidence"]}
                for comment in result["out"]["comments"]:
                    if (set(comment["evidence"]) & {h["chunk_id"] for h in state["hits"]}
                            and system2._comment_allowed(comment, allowed)):
                        tool_citations.update(set(comment["evidence"]) & tool_keys)
                        floor = "medium" if state["policy"]["effective"]["high_risk"] else "low"
                        promoted = {"tag": comment["tag"], "text": comment["text"],
                            "severity": max(comment["severity"], floor, key=chat.LEVELS.index),
                            "evidence": list(comment["evidence"])}
                        accepted_reviews.append(promoted)
                        accepted.append(dict(promoted,
                            evidence=[k for k in comment["evidence"] if k in historical_keys]))
                return dict(result, out=dict(result["out"], comments=accepted))

            answer, trace = chat.respond(
                state["question"], state["history"], state["mode"], index_path=index_path,
                retriever=lambda *_a, **_k: [] if unsupported and state["mode"] == "Groq assessment" else state["hits"], reviewer=enriched_review,
            )
            trace["support"] = support
            if unsupported and state["mode"] == "Groq assessment":
                answer = copy["unsupported_mechanism"] + "\n\n" + ADVISORY
                trace["status"] = "insufficient_evidence"
            elif unsupported:
                answer = copy["unsupported_mechanism"] + "\n\n" + answer
            trace["assessment_tool_citations"] = sorted(tool_citations)
            if trace["status"] == "assessed":
                trace["risk_floor"] = "medium" if state["policy"]["effective"]["high_risk"] else "low"
                trace["assessment"] = {
                    "risk_level": max([trace["risk_floor"]] + [c["severity"] for c in accepted_reviews],
                                      key=chat.LEVELS.index),
                    "review_questions": accepted_reviews,
                }
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
        trace["mcp"] = bundle.get("metrics", {"status":"unavailable","attempted":None,"failed":None})
        return {"answer": answer.strip(), "trace": trace}

    async def output_guard(state):
        def discard(result):
            # Withhold stale/unsafe content while retaining actual work/cost
            # accounting. An output fallback does not undo a completed call.
            prior=state["trace"]
            result["trace"].update({k:prior[k] for k in ("mcp","provider_used","request_attempted") if k in prior})
            state.update(result)
        if "memory_record" in state:
            try:
                settings=policy_settings()
                latest = store.read(state["service"])
                if (latest != state["memory_record"] or effective_policy(state["service"], latest,team_settings=settings) != state["policy"]
                        or (caches is not None and not caches.sources_current(cache_events,index_path))):
                    discard(_answer(copy["stale_context"], "context_changed"))
                    state.pop("memory_record",None)
            except (MemoryUnavailable, ValueError, OSError):
                discard(_answer(copy["memory_unavailable"], "memory_unavailable"))
                state.pop("memory_record",None)
        if "memory_record" in state:
            record, policy = state["memory_record"], state["policy"]
            state["trace"]["memory"] = {"status": "recalled" if record else "empty", "record": record,
                                      "effective_policy": policy}
            if record:
                sections = []
                if record["high_risk"] is not None:
                    sections.append(copy["memory_flag"].format(service=state["service"],
                        flag=str(record["high_risk"]).lower(), effective=str(policy["effective"]["high_risk"]).lower(),
                        source=policy["sources"]["high_risk"]))
                if record["freeze_notes"]:
                    # Inert quoted presentation, never sent as model instructions.
                    note = html.escape(record["freeze_notes"])
                    note = re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", note)
                    sections.append(copy["memory_note"].format(note=note))
                if policy["conflicts"]:
                    sections.append(copy["memory_conflict"])
                state["answer"] = state["answer"].removesuffix(ADVISORY).rstrip() + "\n\n" + "\n\n".join(sections) + "\n\n" + ADVISORY
        responses.guard([state["answer"], state["trace"]])
        if state["trace"].get("status") != "guardrails_unavailable":
            refused = await rail_check("output", {"answer": state["answer"], "trace": state["trace"]})
            if refused:
                discard(refused)
        state["trace"]["rails"] = list(rails.events)
        if caches is not None:
            state["trace"]["cache"] = list(cache_events)
        return {"answer": state["answer"], "trace": state["trace"]}

    builder = StateGraph(State)
    for name, node in (("classify", classify), ("legacy", legacy), ("retrieve", retrieval),
                       ("tools", tools_node), ("compose", compose), ("output_guard", output_guard)):
        builder.add_node(name, timed(name,node))
    builder.add_node("memory_read", timed("memory_read",memory_read))
    builder.add_node("memory_write", timed("memory_write",memory_write))
    builder.add_edge(START, "classify")
    builder.add_conditional_edges("classify", lambda s: s["route"],
                                  {"done": "output_guard", "legacy": "legacy", "memory_read": "memory_read", "memory_write": "memory_write"})
    builder.add_conditional_edges("memory_read", lambda s: s["route"],
                                 {"done": "output_guard", "legacy": "legacy", "retrieve": "retrieve", "tools": "tools"})
    builder.add_edge("memory_write", "output_guard")
    builder.add_conditional_edges("retrieve", lambda s: s["route"],
                                  {"done": "output_guard", "tools": "tools"})
    builder.add_edge("legacy", "output_guard")
    builder.add_edge("tools", "compose")
    builder.add_edge("compose", "output_guard")
    builder.add_edge("output_guard", END)
    return builder.compile()


async def arespond(question, history=None, mode="Local evidence only", *, session_id=None, telemetry_store=None, transport="cli", trace_exporter=None, **collaborators):
    """Only final guarded answer and trace leave this boundary; no raw state."""
    request_id = uuid4().hex
    began=perf_counter();spans=[]
    started_at = datetime.now(timezone.utc).isoformat()
    try:
        if transport not in TRANSPORTS:raise ValueError("invalid_transport")
        reject_credentials([question, history, mode], additional=tracing_credentials())
        responses.guard([question, history, mode])
        if history is not None and (not isinstance(history, list) or len(history) > 100):
            raise ValueError("Invalid history")
        names = chat._services(question) if isinstance(question, str) else []
        approval = bool(len(names) == 1 and chat._specific_change(question, names[0])
            and not parse_command(question)
            and re.search(r"\b(?:from|to)\s+\d|\b(?:add|remove|replace|rotate|enable|disable)\b", routing.active_request(question))
            and approval_request(question))
        effective_question = advisory_question(question) if approval else question
        # Automatic tracing must never upload raw state, including rail setup.
        with tracing_context(enabled=False):
            graph = build_workflow(**collaborators,spans=spans)
            result = await graph.ainvoke({"question": effective_question, "history": history or [], "mode": mode},
                                        config={"recursion_limit": 10, "callbacks": []})
        trace = result["trace"]
        trace.setdefault("mcp", {"status":"unavailable","attempted":None,"failed":None}
            if any(s["stage"]=="tools" for s in spans) else {"status":"not_accessed","attempted":0,"failed":0})
        if approval:
            result["answer"] = load_copy()["approval_continuation"] + "\n\n" + result["answer"]
            trace["approval_declined"] = True
        trace.setdefault("provider_used", False)
        trace.setdefault("request_attempted", False)
        trace.setdefault("memory", {"status": "not_accessed"})
        trace.update(request_id=request_id, session_id=session_id or uuid4().hex, orchestration="langgraph")
        trace["transport"]=transport
        trace["turn"] = 1 + sum(1 for item in (history or []) if isinstance(item, dict) and item.get("role") == "user")
        trace["review_mode"] = mode
        trace["duration_ms"]=round((perf_counter()-began)*1000,3)
        trace["spans"]=spans+[
            {"stage":"rail_"+e["stage"],"duration_ms":e["duration_ms"],"outcome":e["outcome"]} for e in trace.get("rails",[])]+[
            {"stage":"cache_"+e["layer"],"duration_ms":e.get("duration_ms",0),"outcome":e["outcome"]} for e in trace.get("cache",[])]
        for item in [*trace["spans"],*trace.get("events",[]),*trace.get("rails",[]),*trace.get("cache",[])]:
            item["request_id"]=request_id
        if telemetry_store is not None:
            try:
                telemetry_store.write(trace)
                trace["telemetry_status"]="recorded"
            except TelemetryUnavailable:
                result["answer"]=load_copy()["telemetry_failure"]+"\n\n"+ADVISORY
                trace.update(status="telemetry_unavailable",telemetry_status="unavailable")
                trace.pop("assessment",None)
        responses.guard([result["answer"], trace])
        trace.update(started_at=started_at, ended_at=datetime.now(timezone.utc).isoformat())
        try:
            trace["langsmith"] = (trace_exporter or EXPORTER).submit(trace)
        except Exception:
            trace["langsmith"] = {"status": "unavailable"}
        return result["answer"], trace
    except Exception:
        # Failure text is deliberately static even if a catalog/graph is corrupt.
        return ("The request could not be processed. No risk indication is assigned. "
                "This is advisory only; a human decision is required.",
                {"status": "unavailable", "request_id": request_id, "retrieved": [],
                 "provider_used": False, "request_attempted": False,"transport":transport,
                 "mcp":{"status":"unavailable","attempted":None,"failed":None}})


def respond(question, history=None, mode="Local evidence only", **collaborators):
    return anyio.run(lambda: arespond(question, history, mode, **collaborators))
