"""Stopped request workers cannot start late provider calls; ceilings stay local."""

from copy import deepcopy
from threading import Event
from types import SimpleNamespace

import anyio
import pytest

from cra2 import config, system2
from week1 import provider
from week2 import tools, workflow
from week2.execution import ExecutionOptions

CHANGE = "Change checkout-service config timeout from 4 seconds to 400 milliseconds."
HIT = {"chunk_id": "pm-cx101#chunk-001", "doc_id": "pm-cx101", "title": "Timeout incident",
       "source": "week1/corpus/pm-cx101-checkout-timeout.md", "kind": "postmortem",
       "service": "checkout-service", "source_dataset": "corpus_markdown", "score": 0.9,
       "text": "Short payment timeouts abandoned authorisations; verify reconciliation."}


class EmptyMemory:
    def read(self, _service):
        return None


async def local_tools(calls):
    return {"status": "ok", "outputs": {
        name: getattr(tools, name)(**arguments) for name, arguments in calls}, "events": []}


@pytest.fixture
def blocked_before_review(monkeypatch):
    entered, release, exited = Event(), Event(), Event()
    calls = []
    original = workflow.chat.respond

    def blocked(*args, **kwargs):
        entered.set()
        try:
            if not release.wait(5):
                raise AssertionError("Test did not release the compose worker")
            return original(*args, **kwargs)
        finally:
            exited.set()

    def review(_payload, _weights):
        calls.append("dispatched")
        return {"out": {"comments": [{"tag": "history", "severity": "medium",
            "text": "Could shorter timeouts repeat the historical failure?",
            "evidence": [HIT["chunk_id"]]}]}, "tokens": [0, 0],
            "cache_hit": False, "request_attempted": False}

    def no_live(*_args, **_kwargs):
        pytest.fail("Lifecycle tests must not use a provider")

    monkeypatch.setattr(workflow.chat, "respond", blocked)
    monkeypatch.setattr(system2, "_protected_client", no_live)
    arguments = {"mode": "Groq assessment", "context_mode": "sac",
        "retriever": lambda *_a, **_k: [deepcopy(HIT)], "reviewer": review,
        "tool_runner": local_tools, "memory_store": EmptyMemory()}
    try:
        yield entered, release, exited, calls, arguments
    finally:
        release.set()
        if entered.is_set():
            assert exited.wait(5), "Abandoned test worker did not finish"


def test_deadline_prevents_provider_dispatch_from_abandoned_compose_worker(blocked_before_review):
    entered, release, exited, calls, arguments = blocked_before_review
    _, trace = workflow.respond(CHANGE, **arguments,
        execution_options=ExecutionOptions(deadline_seconds=1))
    # Synchronization confirms that the deadline stopped an in-flight compose
    # worker. No elapsed-time performance threshold is asserted.
    assert entered.is_set()
    assert trace["status"] == "unavailable"
    assert trace["request_attempted"] is False
    assert trace["execution"]["model_action_count"] == 0
    release.set()
    assert exited.wait(5)
    assert calls == []


def test_external_task_cancellation_prevents_late_provider_dispatch(blocked_before_review):
    entered, release, exited, calls, arguments = blocked_before_review

    async def scenario():
        finished = Event()
        async def request():
            try:
                await workflow.arespond(CHANGE, **arguments,
                    execution_options=ExecutionOptions(deadline_seconds=10))
            finally:
                finished.set()
        async with anyio.create_task_group() as group:
            group.start_soon(request)
            assert await anyio.to_thread.run_sync(entered.wait, 5)
            group.cancel_scope.cancel()
        assert finished.is_set()
        release.set()
        assert await anyio.to_thread.run_sync(exited.wait, 5)

    anyio.run(scenario)
    assert calls == []


def test_explicit_cancellation_prevents_late_provider_dispatch(blocked_before_review):
    entered, release, exited, calls, arguments = blocked_before_review
    cancel = Event()

    async def scenario():
        result = []
        async def request():
            result.append(await workflow.arespond(CHANGE, **arguments, cancel_event=cancel,
                execution_options=ExecutionOptions(deadline_seconds=10)))
        async with anyio.create_task_group() as group:
            group.start_soon(request)
            assert await anyio.to_thread.run_sync(entered.wait, 5)
            cancel.set()
        assert result[0][1]["status"] == "unavailable"
        assert result[0][1]["request_attempted"] is False
        release.set()
        assert await anyio.to_thread.run_sync(exited.wait, 5)

    anyio.run(scenario)
    assert calls == []


@pytest.mark.parametrize("kwargs", [
    {"timeout": True}, {"timeout": 0}, {"timeout": float("nan")},
    {"timeout": float("inf")}, {"max_tokens": True}, {"max_tokens": 0},
    {"max_tokens": 1.5},
])
def test_provider_ceiling_validation_precedes_client_access(monkeypatch, kwargs):
    monkeypatch.setattr(system2, "_protected_client",
                        lambda: pytest.fail("Invalid ceilings must not construct a client"))
    with pytest.raises(ValueError):
        provider.assess({}, {}, **kwargs)


def test_provider_host_ceilings_can_only_reduce_configured_limits(monkeypatch):
    captured = []
    monkeypatch.setattr(config, "MAX_TOKENS", 512)
    monkeypatch.setattr(config, "TIMEOUT_S", 8)
    monkeypatch.setattr(system2, "_protected_client", lambda: SimpleNamespace(api_key=None))
    def fake_request(_payload, settings, _sdk, _credentials):
        captured.append(settings)
        return {"out": {"comments": []}, "tokens": [0, 0]}
    monkeypatch.setattr(system2, "_request", fake_request)
    provider.assess({}, {}, timeout=30, max_tokens=2048)
    provider.assess({}, {}, timeout=.25, max_tokens=32)
    assert [(item["timeout"], item["max_tokens"]) for item in captured] == [(8, 512), (.25, 32)]
