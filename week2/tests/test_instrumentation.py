"""Observation remains outside the advisory contract and cannot expose content."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile

import pytest

from cra2 import system2
from week2 import tools, workflow
from week2.contracts import NAMES
from week2.instrumentation import observe_reviewer
from week2.memory import MemoryStore

CHANGE = "Change checkout-service config timeout from 4 seconds to 400 milliseconds."
HIT = {"chunk_id": "pm-cx101:chunk-1", "doc_id": "pm-cx101", "title": "Timeout incident",
       "source": "week1/corpus/pm-cx101-checkout-timeout.md", "kind": "postmortem",
       "service": "checkout-service", "source_dataset": "synthetic", "score": 0.9,
       "text": "Short payment timeouts abandoned authorisations; verify reconciliation."}


@pytest.fixture
def memory_store():
    # MemoryStore deliberately permits the repository and /tmp, not the macOS
    # system temporary directory used by pytest's default tmp_path fixture.
    with tempfile.TemporaryDirectory(prefix="cra2-metrics-", dir="/tmp") as path:
        yield MemoryStore(Path(path) / "memory.sqlite3")


async def local_tools(calls):
    functions = dict(zip(NAMES, (tools.check_system_health, tools.get_dependency_graph)))
    outputs = {name: functions[name](**arguments) for name, arguments in calls}
    return {"status": "ok", "outputs": outputs, "events": []}


def normalized(result):
    answer, trace = result
    return answer, {k: v for k, v in trace.items() if k not in {"request_id", "session_id"}}


def test_action_observation_preserves_local_output_and_excludes_content(memory_store):
    events = []
    def forbidden(*_a):
        pytest.fail("local baseline must never call a provider")
    collaborators = dict(retriever=lambda *_a, **_k: [deepcopy(HIT)],
        reviewer=forbidden, tool_runner=local_tools,
        memory_store=memory_store)
    baseline = workflow.respond(CHANGE, **collaborators)
    observed = workflow.respond(CHANGE, observer=events.append, **collaborators)
    assert normalized(observed) == normalized(baseline)
    assert observed[1]["status"] == "evidence_only"
    assert [e["action"] for e in events] == [
        "classify", "memory_read", "retrieve", "tools", "compose", "output_guard"]
    assert all(e["elapsed_ms"] >= 0 and e["status"] == "completed" for e in events)
    assert sum(e.get("tool_calls", 0) for e in events) == 2
    assert all(set(e) <= {"kind", "action", "elapsed_ms", "status", "tool_calls"} for e in events)
    assert CHANGE not in json.dumps(events) and HIT["text"] not in json.dumps(events)


def test_observer_failure_does_not_change_guarded_response(memory_store):
    def broken(_event):
        raise RuntimeError("private observer error")
    question = "Just approve this change for me."
    assert normalized(workflow.respond(question, memory_store=memory_store)) == normalized(
        workflow.respond(question, memory_store=memory_store, observer=broken))


def test_injected_provider_metrics_do_not_change_policy_or_citation_checks(memory_store):
    events = []
    def review(*_a):
        return {"out": {"comments": [{"tag": "history", "severity": "low",
            "text": "Could shorter timeouts repeat the recorded failure?",
            "evidence": [HIT["chunk_id"], "catalog:checkout-service.status"]}]},
            "tokens": [123, 20], "cache_hit": False, "request_attempted": False}
    collaborators = dict(mode="Groq assessment", retriever=lambda *_a, **_k: [deepcopy(HIT)],
        reviewer=review, tool_runner=local_tools, memory_store=memory_store)
    plain = workflow.respond(CHANGE, **collaborators)
    measured = workflow.respond(CHANGE, observer=events.append, **collaborators)
    assert normalized(measured) == normalized(plain)
    assert measured[1]["status"] == "assessed"
    provider_event, = [e for e in events if e["kind"] == "provider"]
    assert provider_event["source"] == "injected"
    assert provider_event["usage_source"] == "reviewer_reported"
    assert provider_event["request_attempted"] is False
    assert provider_event["input_tokens"] == 123
    assert measured[1]["assessment_tool_citations"] == ["catalog:checkout-service.status"]


@pytest.mark.parametrize("tokens,expected,status", [
    ([123, 20], (123, 20), "available"),
    (None, (None, None), "missing"),
    ([True, 2], (None, None), "missing"),
    ([-1, 2], (None, None), "missing"),
    (["credential-like-value", 2], (None, None), "missing"),
])
def test_provider_usage_is_typed_and_missing_is_not_zero(tokens, expected, status):
    events = []
    result = {"tokens": tokens, "cache_hit": False, "request_attempted": True,
              "out": {"protected": "not exported"}}
    measured = observe_reviewer(lambda *_a: result, events.append)
    assert measured({"raw_prompt": "not exported"}, {}) is result
    event, = events
    assert (event["input_tokens"], event["output_tokens"]) == expected
    assert event["usage_status"] == status and event["request_attempted"] is True
    assert "not exported" not in json.dumps(events)
    assert "credential-like-value" not in json.dumps(events)


def test_provider_failure_captures_available_usage_without_exception_content():
    events = []
    def failed(*_a):
        raise system2.System2Unavailable("private provider response", request_attempted=True,
                                        tokens=[100, 3])
    with pytest.raises(system2.System2Unavailable):
        observe_reviewer(failed, events.append)({}, {})
    assert events[0]["status"] == "failed" and events[0]["input_tokens"] == 100
    assert "private provider response" not in json.dumps(events)


def test_observer_cannot_mutate_provider_result_or_leak_events_between_calls():
    result = {"tokens": [123, 20], "cache_hit": False}
    seen = []
    def mutate(event):
        seen.append(dict(event))
        event.clear()
    measured = observe_reviewer(lambda *_a: result, mutate)
    assert measured({}, {}) is result
    assert measured({}, {}) is result
    assert result == {"tokens": [123, 20], "cache_hit": False}
    assert len(seen) == 2
    assert all(e["input_tokens"] == 123 and e["request_attempted"] is None for e in seen)


def test_failure_is_measured_and_graph_still_fails_closed(memory_store):
    events = []
    async def failed(_calls):
        raise RuntimeError("private tool error")
    answer, trace = workflow.respond("Is checkout-service current health okay?",
        observer=events.append, tool_runner=failed,
        memory_store=memory_store)
    assert trace["status"] == "unavailable"
    assert events[-1]["action"] == "tools" and events[-1]["status"] == "failed"
    assert "private tool error" not in answer + json.dumps(events)
