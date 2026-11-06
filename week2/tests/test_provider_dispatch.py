"""No-network checks at the final SDK dispatch boundary, after client setup."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from types import SimpleNamespace

import anyio
import pytest

from cra2 import system2
from week2 import execution, workflow
from week2.execution import ExecutionOptions
from week2.memory import MemoryStore
from week2.tests.test_execution import CHANGE, Collaborators


@pytest.fixture
def memory_store():
    with TemporaryDirectory(prefix="cra2-provider-dispatch-", dir="/tmp") as directory:
        yield MemoryStore(Path(directory) / "memory.sqlite3")


def fake_response(request):
    payload = json.loads(request["messages"][1]["content"])
    content = {"ratings": {key: "low" for key in (
        "deploy_order", "rollback", "config_drift", "dependencies", "monitoring")},
        "comments": [{"tag": "history", "severity": "low",
            "text": f"Could reconciliation check {number} verify the proposed change?",
            "evidence": [payload["incidents"][0]["chunk_id"]]} for number in (1, 2, 3)]}
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop",
        message=SimpleNamespace(content=json.dumps(content), refusal=None))])


def test_cancel_during_client_setup_prevents_late_sdk_dispatch(memory_store, monkeypatch):
    entered, release, finished, dispatched, cancel = (Event() for _ in range(5))
    collaborators = Collaborators()
    original_request = system2._request

    def create(**request):
        dispatched.set()
        return fake_response(request)

    def slow_client():
        entered.set()
        assert release.wait(3), "test did not release fake client setup"
        return SimpleNamespace(api_key=None,
            chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    def monitored_request(*args, **kwargs):
        try:
            return original_request(*args, **kwargs)
        finally:
            finished.set()

    monkeypatch.setattr(system2, "_protected_client", slow_client)
    monkeypatch.setattr(system2, "_request", monitored_request)

    async def run():
        async def trigger_cancel():
            assert await anyio.to_thread.run_sync(entered.wait, 2)
            cancel.set()
        async with anyio.create_task_group() as group:
            group.start_soon(trigger_cancel)
            result = await workflow.arespond(CHANGE, mode="Groq assessment",
                context_mode="sac", cancel_event=cancel, memory_store=memory_store,
                retriever=collaborators.retrieve, tool_runner=collaborators.run_tools)
        return result

    try:
        answer, trace = anyio.run(run)
        assert trace["status"] == "unavailable" and "No risk indication" in answer
        assert trace["execution"]["status"] == "stopped"
        assert not dispatched.is_set()
    finally:
        release.set()
        assert finished.wait(2), "abandoned fake provider worker did not finish"
    assert not dispatched.is_set(), "SDK request began after cancellation returned"


def test_provider_timeout_uses_remaining_deadline_after_client_setup(memory_store, monkeypatch):
    now, requests = [100.0], []
    collaborators = Collaborators()
    monkeypatch.setattr(execution, "monotonic", lambda: now[0])
    monkeypatch.setattr(workflow, "monotonic", lambda: now[0])

    def create(**request):
        requests.append(request)
        return fake_response(request)

    def slow_client():
        # Advance only the host clock: deterministic, without sleeping or network.
        now[0] += .4
        return SimpleNamespace(api_key=None,
            chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    monkeypatch.setattr(system2, "_protected_client", slow_client)
    _, trace = workflow.respond(CHANGE, mode="Groq assessment", context_mode="sac",
        execution_options=ExecutionOptions(deadline_seconds=1, max_output_tokens=64),
        memory_store=memory_store, retriever=collaborators.retrieve,
        tool_runner=collaborators.run_tools)
    assert trace["status"] == "assessed"
    request, = requests
    assert request["timeout"] == pytest.approx(.6)
    assert request["max_completion_tokens"] <= 64


def test_action_metrics_include_exact_dispatched_prompt_and_payload_bytes(memory_store, monkeypatch):
    requests, events = [], []
    collaborators = Collaborators()
    def create(**request):
        requests.append(request)
        return fake_response(request)
    monkeypatch.setattr(system2, "_protected_client", lambda:
        SimpleNamespace(api_key=None, chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    _, trace = workflow.respond(CHANGE, mode="Groq assessment", context_mode="sac",
        memory_store=memory_store, retriever=collaborators.retrieve,
        tool_runner=collaborators.run_tools, observer=events.append)
    assert trace["status"] == "assessed"
    request, = requests
    actions = [event for event in events if event["kind"] == "execution_action"]
    assess, = [event for event in actions if event["action"] == "assess"]
    # Context budget means serialized message content, not the HTTP/schema
    # envelope and not tokenizer usage. Compare exactly what the fake SDK got.
    expected = sum(len(message["content"].encode("utf-8")) for message in request["messages"])
    assert assess["context_bytes"] == expected
    assert sum(event["context_bytes"] for event in actions) == trace["execution"]["input_context_bytes"]
    assert trace["execution"]["peak_context_bytes"] == max(event["context_bytes"] for event in actions)
