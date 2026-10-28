"""Selected earlier traces remain immutable snapshots of their original mode."""

from copy import deepcopy
from secrets import token_hex

from week2 import app


def record(turn, mode="Local evidence only", request=None):
    return {"turn": turn, "review_mode": mode, "question": f"Question {turn}",
            "request_id": request or f"request-{turn}", "status": "help",
            "response_details": "Supporting details", "retrieved": [], "events": [],
            "provider_used": False, "request_attempted": False}


def test_select_earlier_turn_preserves_original_mode_without_execution(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Viewing a saved trace must not run the agent")
    monkeypatch.setattr(app, "respond", forbidden)
    first = record(1)
    second = record(2, "Groq assessment")
    history = app.retain_trace(app.retain_trace([], first), second)
    summary, trace, details, panel = app.select_trace(1, history)
    assert trace == first and "Turn #1" in summary and "Local evidence only" in summary
    assert details == first["response_details"] and "Turn #1" in panel["label"]
    assert app.trace_choices(history) == [("Turn #1 · Local evidence only", 1), ("Turn #2 · Groq assessment", 2)]
    assert history[1] == second


def test_retry_replaces_same_turn_and_prunes_abandoned_future():
    history = [record(1), record(2), record(3)]
    original = deepcopy(history)
    updated = app.retain_trace(history, record(2, "Groq assessment", "retried"))
    assert [item["turn"] for item in updated] == [1, 2]
    assert updated[-1]["request_id"] == "retried" and updated[-1]["review_mode"] == "Groq assessment"
    assert history == original


def test_trace_history_is_bounded_and_projects_only_guarded_fields():
    history = []
    for turn in range(1, 56):
        history = app.retain_trace(history, dict(record(turn), raw_sdk=object(), prompt="not exported"))
    assert len(history) == 50 and history[0]["turn"] == 6
    assert all("raw_sdk" not in item and "prompt" not in item for item in history)
    summary, trace, details, _ = app.select_trace(1, history)
    assert trace == {} and details == "" and summary == app.EMPTY_TRACE


def test_rejected_credential_input_is_not_copied_into_trace_history(monkeypatch):
    secret = token_hex(24)
    monkeypatch.setenv("GROQ_API_KEY", secret)
    answer, _, trace = app.ui_reply(secret, [], "Local evidence only", "test")
    assert trace["status"] == "unavailable" and trace["question"] == "Input withheld"
    assert secret not in answer + str(app.retain_trace([], trace))
