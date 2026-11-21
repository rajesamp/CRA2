"""Guided intake collects explicit facts, without broadening the risk path."""

from inspect import unwrap
from types import SimpleNamespace

import pytest

from cra2.advisor import CATALOG, RULES
from week2 import app, intake
from week2.memory import MemoryStore


ANSWERS = ["checkout-service", "Config change", "Change timeout from 4 seconds to 400 milliseconds.",
           "2026-12-01 10:00 UTC", "Canary 5% then increase gradually", "Restore 4 seconds on elevated errors",
           "Track p95 latency and error rate"]


def completed(fields):
    draft = intake.new_draft()
    for answer in ANSWERS:
        draft = intake.advance(draft, answer, fields)
    return draft


def test_schema_and_progressive_packet_are_deterministic():
    fields = intake.load_schema()
    assert set(intake.choices(fields[0])) == set(CATALOG)
    assert set(intake.choices(fields[1])) == set(RULES["system1"]["change_type"])
    first = intake.new_draft()
    second = intake.advance(first, ANSWERS[0], fields)
    assert first == {"step": 0, "values": {}}
    assert second == {"step": 1, "values": {"service": "checkout-service"}}
    with pytest.raises(ValueError):
        intake.review_question(second, fields)
    final = completed(fields)
    assert final["step"] == 7
    assert final["values"] == dict(zip((f["key"] for f in fields), ANSWERS))
    question = intake.review_question(final, fields)
    assert question == "Assess the risk of changing checkout-service: " + ANSWERS[2]
    assert ANSWERS[4] not in question  # Human notes aren't verified assessment evidence.
    assert intake.new_draft()["values"] == {}


def test_revision_and_invalid_inputs():
    fields = intake.load_schema()
    original = intake.new_draft()
    for answer in ("unknown-service", "", None, "x" * 101):
        with pytest.raises(ValueError):
            intake.advance(original, answer, fields)
    draft = intake.advance(original, ANSWERS[0], fields)
    with pytest.raises(ValueError):
        intake.advance(draft, "new invented type", fields)
    draft = intake.advance(draft, ANSWERS[1], fields)
    for answer in ("something", "new config", "timeout\x00 to 1 second", "x" * 601):
        with pytest.raises(ValueError):
            intake.advance(draft, answer, fields)
    final = completed(fields)
    revised = intake.previous(final)
    with pytest.raises(ValueError):
        intake.review_question(revised, fields)
    revised = intake.advance(revised, "Not yet defined", fields)
    assert revised["values"]["monitoring_plan"] == "Not yet defined"
    assert final["values"]["monitoring_plan"] == ANSWERS[-1]
    assert intake.open_items(revised) == ["Monitoring plan"]
    assert "Explicitly unresolved" in app.intake_view(revised, fields)[1]
    assert intake.open_items(final) == []


def test_malformed_schema_fails_closed(tmp_path):
    schema = tmp_path / "invalid.json"
    schema.write_text('{"version": 1, "fields": []}')
    with pytest.raises(ValueError):
        intake.load_schema(schema)


class Gate:
    def __init__(self, blocked=False):
        self.blocked = blocked
        self.calls = []

    def admit(self, answer, client):
        self.calls.append((answer, client))
        return {"blocked": self.blocked}

    def remaining(self, client):
        return (15, "adversarial") if self.blocked else (0, "")


def test_blocked_answer_is_not_retained_or_echoed():
    fields = intake.load_schema()
    draft = intake.new_draft()
    for answer in ANSWERS[:2]:
        draft = intake.advance(draft, answer, fields)
    gate = Gate(blocked=True)
    blocked_text = "blocked-input-canary"
    view = app.advance_intake(draft, None, blocked_text, fields, gate, "client")
    assert gate.calls == [(blocked_text, "client")]
    assert view[0] == draft and blocked_text not in str(view)
    assert "Input withheld" in view[-1]


def test_ui_handoff_is_explicit_and_no_provider_call(tmp_path, monkeypatch):
    gate = Gate()
    demo = app.build_app(memory_store=MemoryStore(tmp_path / "memory.sqlite3"), abuse_gate=gate)
    try:
        def unexpected(*args, **kwargs):
            pytest.fail("Intake must not run a review")
        monkeypatch.setattr(app, "guarded_ui_reply", unexpected)
        callbacks = {fn.fn.__name__: unwrap(fn.fn) for fn in demo.fns.values() if fn.fn}
        request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
        draft = intake.new_draft()
        for index, value in enumerate(ANSWERS):
            result = callbacks["intake_next"](draft, value if index < 2 else None,
                                                "" if index < 2 else value, request)
            draft = result[0]
        question, feedback = callbacks["intake_to_chat"](draft, request)
        assert question == intake.review_question(draft, intake.load_schema())
        assert "then send" in feedback
        assert len(gate.calls) == 7
        gate.blocked = True
        question, feedback = callbacks["intake_to_chat"](draft, request)
        assert "security pause" in feedback and "value" not in question
    finally:
        demo.close()
