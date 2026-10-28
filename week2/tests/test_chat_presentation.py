"""User replies stay concise while the same turn retains guarded diagnostics."""

from copy import deepcopy
from secrets import token_hex

import pytest

from cra2 import system2
from cra2.advisor import ADVISORY
from week2 import app, workflow
from week2.memory import MemoryStore

QUESTION = "How risky is changing checkout-service config timeout from 4 seconds to 400 milliseconds?"
HIT = {"chunk_id": "pm-cx101:chunk-1", "doc_id": "pm-cx101", "title": "Timeout incident",
       "source": "week1/corpus/pm-cx101-checkout-timeout.md", "kind": "postmortem",
       "service": "checkout-service", "source_dataset": "synthetic", "score": 0.9,
       "text": "Short payment timeouts abandoned authorisations; verify reconciliation."}


@pytest.mark.parametrize("mode,status,review_level,expected_level", [
    ("Local evidence only", "evidence_only", "high", None),
    ("Groq assessment", "assessed", "high", "HIGH"),
    ("Groq assessment", "assessed", "low", "MEDIUM"),
])
def test_assessment_chat_keeps_details_in_same_turn_trace(mode, status, review_level, expected_level, monkeypatch, tmp_path):
    monkeypatch.setenv("GROQ_API_KEY", token_hex(24))
    monkeypatch.delenv("CRA2_ENV_FILE", raising=False)
    monkeypatch.setattr(system2, "client", lambda: pytest.fail("No live provider in presentation tests"))
    monkeypatch.setattr(workflow.chat, "search", lambda *_a, **_k: [deepcopy(HIT)])

    def review(payload, _weights):
        assert set(payload["tool_results"]) == {"check_system_health", "get_dependency_graph"}
        return {"out": {"comments": [{"tag": "history", "severity": review_level,
                 "text": "Could short timeouts abandon authorisations again?",
                 "hidden_reasoning": "PRIVATE_REVIEW_CANARY",
                 "evidence": [HIT["chunk_id"], "catalog:checkout-service.status"]}]},
                "cache_hit": False, "tokens": [100, 20]}

    monkeypatch.setattr(workflow.provider, "assess", review)
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.write("checkout-service", high_risk=True)
    answer, summary, trace = app.ui_reply(QUESTION, [], mode, "presentation-test", memory_store=store)
    for detail in (HIT["chunk_id"], HIT["text"], "catalog:", "graph:", "memory:",
                   "Healthy", "payment-gateway", "Source:", "Recorded graph", "Try:"):
        assert detail not in answer
    assert len(answer.split()) < 65
    assert "Turn #" not in answer and answer.endswith(ADVISORY)
    assert trace["status"] == status and trace["turn"] == 1
    assert "Turn #1" in summary
    assert HIT["chunk_id"] in trace["response_details"]
    assert "memory:checkout-service.high_risk" in trace["response_details"]
    assert len([e for e in trace["events"] if e["event"] == "tool_result"]) == 2
    assert "PRIVATE_REVIEW_CANARY" not in str(trace)
    if mode == "Groq assessment":
        assert expected_level in answer and trace["assessment"]["risk_level"] == expected_level.lower()
        assert trace["assessment"]["review_questions"][0]["text"].endswith("?")
    else:
        assert "No risk rating" in answer and "Risk indication:" not in answer
        assert trace["provider_used"] is False and trace["request_attempted"] is False


@pytest.mark.parametrize("history,turn", [
    ([], 1),
    ([{"role": "user", "content": "first"}, {"role": "assistant", "content": "reply"}], 2),
    ([{"role": "user", "content": "first"}, {"role": "assistant", "content": "reply"},
      {"role": "user", "content": "second"}, {"role": "assistant", "content": "reply"}], 3),
])
def test_turn_number_follows_visible_history_including_retry_and_new_chat(history, turn, monkeypatch):
    def respond(*_a, **_k):
        return "diagnostic source catalog:checkout-service.status", {
            "status": "evidence_only", "events": [], "retrieved": [],
            "provider_used": False, "request_attempted": False}
    monkeypatch.setattr(app, "respond", respond)
    for _ in range(2):
        answer, summary, trace = app.ui_reply(QUESTION, history, "Local evidence only", "test")
        assert "Turn #" not in answer and f"Turn #{turn}" in summary
        assert trace["turn"] == turn
        assert trace["review_mode"] == "Local evidence only"
        assert "catalog:" not in answer and "catalog:" in trace["response_details"]


def test_assessed_reply_without_validated_level_fails_closed(monkeypatch):
    monkeypatch.setattr(app, "respond", lambda *_a, **_k: (
        "Risk indication: HIGH. private presentation details", {"status": "assessed"}))
    answer, _, _ = app.ui_reply(QUESTION, [], "Groq assessment", "test")
    assert "HIGH" not in answer and "private presentation" not in answer
    assert "No risk rating" in answer


def test_unavailable_response_catalog_does_not_expose_diagnostics(monkeypatch):
    monkeypatch.setattr(app, "respond", lambda *_a, **_k: (
        "supporting diagnostic catalog:checkout-service.status", {"status": "evidence_only"}))
    def unavailable():
        raise ValueError("private catalog detail")
    monkeypatch.setattr(app, "load_copy", unavailable)
    answer, _, trace = app.ui_reply(QUESTION, [], "Local evidence only", "test")
    assert "No risk rating" in answer and "private catalog" not in answer
    assert "supporting diagnostic" not in answer
    assert "supporting diagnostic" in trace["response_details"]
