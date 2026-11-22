"""Graph behavior, evidence/policy preservation, and real MCP integration."""

import json
import os
from copy import deepcopy
from secrets import token_hex

import pytest
from langsmith.utils import tracing_is_enabled

from cra2 import system2
from cra2.advisor import ADVISORY
from week1 import chat
from week2 import workflow

CHANGE = "Change checkout-service config timeout from 4 seconds to 400 milliseconds."
HIT = {"chunk_id": "pm-cx101:chunk-1", "doc_id": "pm-cx101", "title": "Timeout incident",
       "source": "week1/corpus/pm-cx101-checkout-timeout.md", "kind": "postmortem",
       "service": "checkout-service", "source_dataset": "synthetic", "score": 0.9,
       "text": "Short payment timeouts abandoned authorisations; verify reconciliation."}


@pytest.fixture(autouse=True)
def no_provider(monkeypatch, tmp_path):
    from week2.memory import MemoryStore
    store = MemoryStore(tmp_path / "preferences.sqlite3")
    monkeypatch.setattr(workflow, "MemoryStore", lambda: store)
    monkeypatch.setenv("GROQ_API_KEY", token_hex(24))
    monkeypatch.delenv("CRA2_ENV_FILE", raising=False)
    monkeypatch.setattr(system2, "client", lambda: pytest.fail("no live provider in tests"))


def forbidden(*_a, **_k):
    pytest.fail("request should terminate before external work")


@pytest.mark.parametrize("question,status", [
    ("What's the capital of France?", "out_of_scope"),
    ("Just approve this change for me.", "advisory_boundary"),
    ("Remember checkout-service is high-risk for our team.", "memory_saved"),
    ("How risky is changing checkout-service?", "needs_clarification"),
    ("Is this a freeze window right now?", "needs_clarification"),
    ("Is unknown-service current health okay?", "needs_clarification"),
    ("", "needs_clarification"),
])
def test_early_exit_without_retrieval_mcp_or_provider(question, status):
    answer, trace = workflow.respond(question, retriever=forbidden, reviewer=forbidden,
                                     tool_runner=forbidden)
    assert trace["status"] == status
    assert trace["orchestration"] == "langgraph"
    if status != "out_of_scope": assert answer.endswith(ADVISORY)


def test_real_graph_and_both_mcp_tools_feed_reviewer():
    seen = []

    def review(payload, _weights):
        seen.append(deepcopy(payload))
        assert set(payload["tool_results"]) == {"check_system_health", "get_dependency_graph"}
        assert "graph:checkout-service.dependencies" in payload["evidence_keys"]
        return {"out": {"comments": [{"tag": "history", "severity": "medium",
                  "text": "Could shorter timeouts repeat the recorded failure?",
                  "evidence": [HIT["chunk_id"], "catalog:checkout-service.status"]}]},
                "cache_hit": False, "tokens": [100, 20]}

    answer, trace = workflow.respond(CHANGE, mode="Groq assessment",
        retriever=lambda *_a, **_k: [deepcopy(HIT)], reviewer=review)
    assert len(seen) == 1 and trace["status"] == "assessed"
    assert len([e for e in trace["events"] if e["event"] == "tool_result"]) == 2
    assert "Healthy" in answer and "payment-gateway" in answer and "synthetic snapshot" in answer
    assert "unknown" in answer and "current production state" in answer
    assert answer.endswith(ADVISORY)


@pytest.mark.parametrize("question,tool", [
    ("What services depend on payment-gateway?", "get_dependency_graph"),
    ("Is checkout-service current health okay?", "check_system_health"),
    ("Is checkout-service in a freeze window?", "check_system_health"),
])
def test_tool_only_queries_do_not_retrieve_or_use_provider(question, tool):
    answer, trace = workflow.respond(question, retriever=forbidden, reviewer=forbidden)
    assert trace["status"] == "tool_evidence"
    assert [e["tool"] for e in trace["events"] if "tool" in e] == [tool]
    assert "Risk indication:" not in answer


def test_local_evidence_mode_both_tools_but_no_reviewer():
    answer, trace = workflow.respond(CHANGE, retriever=lambda *_a, **_k: [deepcopy(HIT)], reviewer=forbidden)
    assert trace["status"] == "evidence_only" and "Risk indication:" not in answer
    assert HIT["chunk_id"] in answer


def test_tool_failure_discards_combined_assessment():
    async def fail(_calls):
        return {"status": "error", "outputs": {}, "events": [{"event": "mcp_failed", "code": "timeout"}]}
    answer, trace = workflow.respond(CHANGE, retriever=lambda *_a, **_k: [deepcopy(HIT)],
                                     reviewer=forbidden, tool_runner=fail)
    assert trace["status"] == "tools_unavailable" and "No combined risk" in answer


def test_provider_failure_keeps_tool_evidence():
    def unavailable(*_a):
        raise system2.System2Unavailable("private detail", request_attempted=True)
    answer, trace = workflow.respond(CHANGE, mode="Groq assessment",
        retriever=lambda *_a, **_k: [deepcopy(HIT)], reviewer=unavailable)
    assert trace["status"] == "provider_unavailable" and "private detail" not in answer
    assert "Healthy" in answer and "Risk indication:" not in answer


def test_unsupported_model_citation_does_not_create_risk():
    def bad(*_a):
        return {"out": {"comments": [{"tag": "history", "severity": "high",
                 "text": "Could it fail?", "evidence": ["fabricated"]}]},
                "cache_hit": False, "tokens": [1, 1]}
    answer, trace = workflow.respond(CHANGE, mode="Groq assessment",
        retriever=lambda *_a, **_k: [deepcopy(HIT)], reviewer=bad)
    assert trace["status"] == "insufficient_evidence" and "Risk indication:" not in answer


def test_credentials_in_input_never_start_work():
    secret = os.environ["GROQ_API_KEY"]
    answer, trace = workflow.respond(secret, retriever=forbidden, reviewer=forbidden, tool_runner=forbidden)
    assert trace["status"] == "unavailable" and secret not in answer + json.dumps(trace)


def test_langsmith_environment_tracing_disabled(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    def retrieve(*_a, **_k):
        assert tracing_is_enabled() is False
        return [deepcopy(HIT)]
    answer, trace = workflow.respond(CHANGE, retriever=retrieve, reviewer=forbidden)
    assert trace["status"] == "evidence_only"


def test_policy_floor_is_preserved():
    def review(payload, _weights):
        return {"out": {"comments": [{"tag": "history", "severity": "low",
                  "text": "Could monitoring verify the proposed change?", "evidence": [HIT["chunk_id"]]}]},
                "cache_hit": False, "tokens": [1, 1]}
    answer, trace = workflow.respond(CHANGE, mode="Groq assessment",
        retriever=lambda *_a, **_k: [deepcopy(HIT)], reviewer=review)
    expected = chat.resolve_settings("checkout-service", chat.CATALOG["checkout-service"], {}, chat.TEAM_SETTINGS)
    assert trace["risk_floor"] == ("medium" if expected["service"]["high_risk"] else "low")


@pytest.mark.parametrize("query", [CHANGE, "Has checkout-service had similar incidents before?"])
@pytest.mark.parametrize("failure", ["policy", "missing", "inconsistent", "exception"])
def test_context_failure_precedes_consumers_and_export(monkeypatch, query, failure):
    from unittest.mock import Mock
    from week3 import guardrails

    marker = "Retired fixture handbook."
    hit = dict(HIT, title=marker)
    selections = []
    rails = guardrails.LocalRails()
    original_check = rails.check

    async def check(stage, payload):
        if stage == "context" and failure != "policy":
            if failure == "exception":
                raise RuntimeError(marker)
            if failure == "inconsistent":
                await original_check(stage, payload)
                return False
            return True  # No receipt from the engine.
        return await original_check(stage, payload)

    if failure == "policy":
        import re
        monkeypatch.setattr(guardrails, "INJECTION", re.compile(re.escape(marker)))
    monkeypatch.setattr(rails, "check", check)
    monkeypatch.setattr(chat, "_compose_hits", forbidden)

    def select(*args, **kwargs):
        selections.append(query)
        return [hit]

    sink, exporter = Mock(), Mock()
    exporter.submit.return_value = {"status": "disabled"}
    answer, trace = workflow.respond(query, retriever=select, reviewer=forbidden,
                                     tool_runner=forbidden, guardrails=rails,
                                     telemetry_store=sink, trace_exporter=exporter)
    assert selections == [query]
    assert trace["status"] == ("guardrail_blocked" if failure == "policy" else "guardrails_unavailable")
    receipt, = [e for e in trace["rails"] if e["stage"] == "context"]
    assert receipt["code"] == ("untrusted_context" if failure == "policy" else "rail_unavailable")
    assert receipt["executed"] == (failure == "policy")
    assert trace["retrieved"] == [] and trace["mcp"]["attempted"] == 0 and not trace["request_attempted"]
    sink.write.assert_called_once()
    exporter.submit.assert_called_once()
    assert marker not in repr((answer, trace, sink.write.call_args, exporter.submit.call_args))


@pytest.mark.parametrize("query", ["List risk scenarios in the dataset, titles only",
                                   "How many scenarios are in the dataset?"])
def test_browse_screens_selected_trace_titles_before_render(monkeypatch, query):
    import re
    from week3 import guardrails

    titles = json.loads((chat.HERE / "scenario_titles.json").read_text())
    marker = next(iter(titles.values()))["title"]
    monkeypatch.setattr(guardrails, "INJECTION", re.compile(re.escape(marker)))
    monkeypatch.setattr(chat.answers, "_render_dataset", forbidden)
    answer, trace = workflow.respond(query, retriever=forbidden, reviewer=forbidden, tool_runner=forbidden)
    assert trace["status"] == "guardrail_blocked" and marker not in repr((answer, trace))
    assert [e["outcome"] for e in trace["rails"] if e["stage"] == "context"] == ["block"]


def test_delegated_history_preserves_checked_originals(monkeypatch):
    hit = dict(HIT, text="Équipe Δ — approved rehearsal notes.\nSecond line.", chunk_id="pm:Å:02")
    batch = [dict(hit)]
    from week3.guardrails import LocalRails
    check = LocalRails.check

    async def update_source(self, stage, payload):
        passed = await check(self, stage, payload)
        if stage == "context":
            batch[0]["text"] = "A later revision."
        return passed

    monkeypatch.setattr(LocalRails, "check", update_source)
    from unittest.mock import Mock
    select = Mock(return_value=batch)
    answer, trace = workflow.respond("Has checkout-service had similar incidents before?",
                                     retriever=select, tool_runner=forbidden, reviewer=forbidden)
    select.assert_called_once()
    assert trace["status"] == "history_only"
    assert trace["retrieved"][0]["text"] == hit["text"]
    assert trace["retrieved"][0]["chunk_id"] == hit["chunk_id"]
    assert trace["retrieved"][0]["source"] == hit["source"]
    assert hit["chunk_id"] in answer
