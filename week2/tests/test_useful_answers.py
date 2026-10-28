"""Reported prompts produce useful outcomes without exposing execution internals."""

from copy import deepcopy

import pytest

from cra2.advisor import ADVISORY
from week2 import app, workflow
from week2.memory import MemoryStore

TIMEOUT = "How risky is changing checkout-service config timeout from 4 seconds to 400 milliseconds?"
RETRIES = "Assess the risk of increasing checkout-service retries from 2 to 5 during peak traffic."
VAGUE = "How risky is deploying a checkout-service release that changes downstream request handling?"
HIT = {"chunk_id": "pm-cx101:chunk-1", "doc_id": "pm-cx101", "title": "Timeout incident",
       "source": "week1/corpus/pm-cx101-checkout-timeout.md", "kind": "postmortem",
       "service": "checkout-service", "source_dataset": "synthetic", "score": 0.9,
       "text": "Short payment timeouts abandoned authorisations; verify reconciliation."}


def forbidden(*_args, **_kwargs):
    pytest.fail("This request must not call the provider or external work")


@pytest.mark.parametrize("question,expected", [
    (TIMEOUT, ("90%", "latency", "cancellation")),
    (RETRIES, ("2", "5", "peak", "backoff", "duplicate")),
])
def test_exact_local_questions_provide_change_facts_and_review_checks(question, expected, monkeypatch, tmp_path):
    monkeypatch.setattr(workflow.chat, "search", lambda *_a, **_k: [deepcopy(HIT)])
    monkeypatch.setattr(workflow.provider, "assess", forbidden)
    answer, _, trace = app.ui_reply(question, [], "Local evidence only", "useful-local",
        memory_store=MemoryStore(tmp_path / "memory.sqlite3"))
    assert trace["status"] == "evidence_only"
    assert len([event for event in trace["events"] if event["event"] == "tool_result"]) == 2
    assert all(word in answer.lower() for word in expected)
    assert "No risk rating" in answer and "Groq assessment" in answer
    assert not trace["request_attempted"] and not trace["provider_used"]
    assert all(detail not in answer for detail in (HIT["text"], HIT["chunk_id"], "catalog:", "memory:", "Recorded graph", "Turn #"))
    assert len(answer.split()) < 65 and answer.endswith(ADVISORY)


def test_overview_is_short_and_does_not_explain_internal_controls():
    answer, trace = workflow.respond("What is this app?", retriever=forbidden,
                                     reviewer=forbidden, tool_runner=forbidden)
    assert trace["topic"] == "overview" and trace["status"] == "help"
    assert "CRA2 helps" in answer and "change" in answer and "services" in answer
    assert len(answer.split()) < 100
    assert all(word not in answer for word in ("Admin", "Agent trace", "uncalibrated", "MCP", "LangGraph"))


def test_vague_downstream_change_asks_a_targeted_question_with_a_ready_example():
    answer, trace = workflow.respond(VAGUE, retriever=forbidden, reviewer=forbidden, tool_runner=forbidden)
    assert trace["status"] == "needs_clarification"
    assert all(word in answer.lower() for word in ("timeout", "retries", "current", "proposed", "example"))
    assert "retrieved history" not in answer.lower()


def test_groq_reply_includes_a_validated_review_check_without_diagnostics(monkeypatch, tmp_path):
    monkeypatch.setattr(workflow.chat, "search", lambda *_a, **_k: [deepcopy(HIT)])
    check = "Could timeout handling leave payment and order state inconsistent?"
    def review(payload, _weights):
        assert set(payload["tool_results"]) == {"check_system_health", "get_dependency_graph"}
        return {"out": {"comments": [{"tag": "history", "severity": "high", "text": check,
                "hidden_reasoning": "PRIVATE_CANARY", "evidence": [HIT["chunk_id"]]}]},
                "cache_hit": False, "request_attempted": False, "tokens": [0, 0]}
    monkeypatch.setattr(workflow.provider, "assess", review)
    answer, _, trace = app.ui_reply(TIMEOUT, [], "Groq assessment", "useful-groq",
        memory_store=MemoryStore(tmp_path / "memory.sqlite3"))
    assert "HIGH" in answer and check in answer
    assert trace["assessment"]["review_questions"][0]["text"] == check
    assert HIT["chunk_id"] not in answer and "PRIVATE_CANARY" not in str((answer, trace))
    assert len(answer.split()) < 65


@pytest.mark.parametrize("before,after,expected", [
    ("4000 milliseconds", "400 milliseconds", "90%"),
    ("400 milliseconds", "4 seconds", "900%"),
    ("4 seconds", "3.999 seconds", "less than 0.1%"),
    ("4 seconds", "0.001 milliseconds", "more than 99.9%"),
])
def test_timeout_comparison_normalizes_units(before, after, expected):
    trace = {"status": "evidence_only", "question": f"Change checkout-service timeout from {before} to {after}."}
    answer = app.chat_response("PRIVATE_DIAGNOSTICS", trace)
    assert expected in answer and "PRIVATE_DIAGNOSTICS" not in answer


def test_unclear_numeric_comparisons_do_not_invent_a_percentage():
    for question in (
        "Change checkout-service timeout from 0 seconds to 400 milliseconds.",
        "Change checkout-service timeouts from 4 seconds to 400 milliseconds and from 3 seconds to 1 second.",
    ):
        answer = app.chat_response("PRIVATE_DIAGNOSTICS", {"status": "evidence_only", "question": question})
        assert "%" not in answer and "PRIVATE_DIAGNOSTICS" not in answer


def test_model_question_cannot_copy_diagnostic_identifiers_into_chat():
    trace = {"status": "assessed", "question": TIMEOUT, "assessment": {"risk_level": "high",
        "review_questions": [{"text": "Could catalog:checkout-service.status hide a failure?"}]}}
    answer = app.chat_response("PRIVATE_DIAGNOSTICS", trace)
    assert "HIGH" in answer and "catalog:" not in answer


def test_browser_keeps_local_evidence_as_default(tmp_path):
    demo = app.build_app(memory_store=MemoryStore(tmp_path / "memory.sqlite3"))
    try:
        mode = next(c for c in demo.config["components"] if c["type"] == "radio" and c["props"].get("label") == "Review mode")
        assert mode["props"]["value"] == "Local evidence only"
    finally:
        demo.close()
