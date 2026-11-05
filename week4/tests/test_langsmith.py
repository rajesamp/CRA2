"""Real execution, bounded opt-in export, redaction and private trace links."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from threading import Event
from uuid import uuid4

import pytest

from week2.memory import MemoryStore
from week2.workflow import respond
from week4.langsmith_tracing import CheckedClient, LangSmithExporter, Settings, build_runs, safe_url


def snapshot():
    start = datetime.now(timezone.utc)
    return {"request_id": uuid4().hex, "session_id": uuid4().hex, "turn": 2,
            "review_mode": "Local evidence only", "transport": "browser", "status": "evidence_only",
            "started_at": start.isoformat(), "ended_at": (start + timedelta(seconds=1)).isoformat(),
            "memory": {"status": "recalled", "record": {"freeze_notes": "private-note-canary"},
                       "effective_policy": {"team": "private-team-canary", "effective": {"high_risk": True}}},
            "question": "private-question-canary", "response_details": "private-answer-canary",
            "prompt": "private-prompt-canary", "history": ["private-history-canary"],
            "retrieved": [{"chunk_id": "CX-101#chunk-001", "similarity": .8, "text": "private-passage-canary"}],
            "spans": [{"stage": "memory_read", "outcome": "completed", "duration_ms": 2,
                       "started_at": start.isoformat(), "ended_at": (start + timedelta(milliseconds=2)).isoformat()}]}


class Client:
    def __init__(self):
        self.batches = []

    def batch_ingest_runs(self, *, create):
        self.batches.append(deepcopy(create))

    def close(self, **kwargs):
        pass


def test_explicit_enable_and_region_destination_validation(monkeypatch):
    monkeypatch.delenv("CRA2_LANGSMITH_ENABLED", raising=False)
    monkeypatch.setenv("LANGSMITH_API_KEY", "configured-private-key")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    assert Settings.read() is None
    monkeypatch.setenv("CRA2_LANGSMITH_ENABLED", "true")
    assert Settings.read().project == "CRA2"
    assert "configured-private-key" not in repr(Settings.read())
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "https://example.invalid")
    with pytest.raises(ValueError):
        Settings.read()
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "https://eu.api.smith.langchain.com")
    monkeypatch.setenv("LANGSMITH_AGENT_ID", "cra2")
    monkeypatch.setenv("LANGSMITH_AGENT_ENVIRONMENT", "local")
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
    settings = Settings.read()
    assert settings.project is None and settings.environment == "local"
    runs = build_runs(snapshot(), settings)
    assert runs[0]["address"]["kind"] == "AGENT" and "session_name" not in runs[0]
    monkeypatch.setenv("LANGSMITH_PROJECT", "CRA2")
    with pytest.raises(ValueError):
        Settings.read()


def test_projection_excludes_private_content_and_preserves_memory_and_source_ids():
    trace = snapshot()
    runs = build_runs(trace, Settings("fake-key"))
    serialized = json.dumps(runs)
    assert "canary" not in serialized
    assert runs[0]["outputs"]["memory"] == {"status": "recalled", "high_risk": True}
    assert runs[0]["outputs"]["evidence"] == [{"chunk_id": "CX-101#chunk-001", "similarity": .8}]
    assert "Turn #2" in runs[0]["name"]
    assert all(r["extra"]["metadata"]["thread_id"] == str(uuid4_from(trace["session_id"])) for r in runs)
    assert runs[1]["parent_run_id"] == runs[0]["id"]


def uuid4_from(value):
    from uuid import UUID
    return UUID(value)


def test_invalid_projection_never_reaches_client(monkeypatch):
    client = Client()
    exporter = LangSmithExporter(settings_reader=lambda: Settings("fake-key"), client_factory=lambda _: client)
    trace = snapshot()
    trace["spans"][0]["started_at"] = "1900-01-01T00:00:00+00:00"
    assert exporter.submit(trace)["status"] == "unavailable"
    assert not client.batches and exporter.worker is None
    trace = snapshot()
    trace["transport"] = "slack"
    assert exporter.submit(trace)["status"] == "not_enabled_for_transport"
    assert exporter.worker is None


def test_actual_memory_recall_and_mcp_tree_exports_without_raw_graph_state(tmp_path, monkeypatch):
    from langsmith.run_trees import RunTree
    from week3.cache import WorkflowCaches
    monkeypatch.setattr(RunTree, "get_url", lambda _: "https://smith.langchain.com/o/test/projects/p/test/r/test")
    client = Client()
    exporter = LangSmithExporter(settings_reader=lambda: Settings("fake-key"), client_factory=lambda _: client)
    store = MemoryStore(tmp_path / "memory.sqlite3")
    session = uuid4().hex
    caches = WorkflowCaches()
    first = "Remember that checkout-service is always high-risk for our team."
    _, written = respond(first, memory_store=store, session_id=session, transport="browser", trace_exporter=exporter)
    answer, recalled = respond("What services depend on checkout-service?", [{"role": "user", "content": first}],
                              memory_store=store, session_id=session, transport="browser", trace_exporter=exporter, caches=caches)
    assert exporter.flush()
    assert written["status"] == "memory_saved" and recalled["memory"]["status"] == "recalled"
    assert not recalled["request_attempted"] and recalled["turn"] == 2
    assert len(client.batches) == 2
    runs = client.batches[-1]
    assert any(r["run_type"] == "tool" and r["name"] == "get_dependency_graph" for r in runs)
    assert any(r["name"] == "memory_read" and r["outputs"]["memory"]["status"] == "recalled" for r in runs)
    assert any(r["name"] == "guardrail_input" for r in runs)
    assert all(r["extra"]["metadata"]["turn"] == 2 for r in runs)
    assert exporter.status(recalled)["status"] == "submitted"
    assert safe_url(exporter.status(recalled)["url"])
    _, reused = respond("What services depend on checkout-service?", memory_store=store, session_id=session,
                        transport="browser", trace_exporter=exporter, caches=caches)
    assert exporter.flush()
    cached_runs = client.batches[-1]
    assert reused["mcp"]["attempted"] == 0
    assert not any(r["run_type"] == "tool" for r in cached_runs)
    assert any(e["outcome"] == "hit" for r in cached_runs if r["name"] == "tools" for e in r["outputs"]["cache"])


def test_queue_backpressure_is_bounded_and_nonblocking():
    entered, release = Event(), Event()
    class Slow(Client):
        def batch_ingest_runs(self, *, create):
            entered.set()
            assert release.wait(5)
    exporter = LangSmithExporter(settings_reader=lambda: Settings("fake-key"), client_factory=lambda _: Slow(), capacity=1)
    try:
        assert exporter.submit(snapshot())["status"] == "queued"
        assert entered.wait(2)
        assert exporter.submit(snapshot())["status"] == "queued"
        assert exporter.submit(snapshot())["status"] == "queue_full"
    finally:
        release.set()
        assert exporter.flush()


def test_tracing_only_key_url_lookup_failure_keeps_successful_submission():
    client = Client()  # No read/URL API: equivalent to restricted read permission.
    exporter = LangSmithExporter(settings_reader=lambda: Settings("fake-key"), client_factory=lambda _: client)
    trace = snapshot()
    exporter.submit(trace)
    assert exporter.flush()
    assert client.batches and exporter.status(trace)["status"] == "submitted"
    assert "url" not in exporter.status(trace)


def test_link_resolution_keeps_ui_polling_until_private_link_is_ready(monkeypatch):
    from langsmith.run_trees import RunTree
    from week2 import app
    entered, release = Event(), Event()
    def resolve(tree):
        entered.set()
        assert release.wait(5)
        return "https://smith.langchain.com/o/test/r/test"
    monkeypatch.setattr(RunTree, "get_url", resolve)
    exporter = LangSmithExporter(settings_reader=lambda: Settings("fake-key"), client_factory=lambda _: Client())
    monkeypatch.setattr(app, "EXPORTER", exporter)
    trace = snapshot()
    try:
        exporter.submit(trace)
        assert entered.wait(2)
        assert exporter.status(trace)["status"] == "resolving_link"
        text, poll = app.langsmith_view(trace["turn"], [trace])
        assert "Resolving its private link" in text and poll["active"] is True
    finally:
        release.set()
        assert exporter.flush()
    text, poll = app.langsmith_view(trace["turn"], [trace])
    assert "Open this trace in LangSmith" in text and poll["active"] is False


def test_sdk_private_url_fallback_survives_trace_url_endpoint_failure(monkeypatch):
    from langsmith.run_trees import RunTree
    def unavailable(tree):
        raise ValueError("url_endpoint_unavailable")
    monkeypatch.setattr(RunTree, "get_url", unavailable)
    class Fallback(Client):
        def get_run_url(self, **kwargs):
            return "https://smith.langchain.com/o/test/r/test"
    exporter = LangSmithExporter(settings_reader=lambda: Settings("fake-key"), client_factory=lambda _: Fallback())
    trace = snapshot()
    exporter.submit(trace)
    assert exporter.flush()
    assert exporter.status(trace)["url"] == "https://smith.langchain.com/o/test/r/test"


def test_sdk_mutation_does_not_break_private_link_or_change_run_id_type(monkeypatch):
    from langsmith.run_trees import RunTree
    from uuid import UUID
    monkeypatch.setattr(RunTree, "get_url", lambda _: "https://smith.langchain.com/o/test/r/test")
    class Mutating(Client):
        def batch_ingest_runs(self, *, create):
            for run in create:
                run["id"] = UUID(run["id"])
                run["start_time"] = datetime.fromisoformat(run["start_time"])
    exporter = LangSmithExporter(settings_reader=lambda: Settings("fake-key"), client_factory=lambda _: Mutating())
    trace = snapshot()
    exporter.submit(trace)
    assert exporter.flush()
    status = exporter.status(trace)
    assert status.get("url") == "https://smith.langchain.com/o/test/r/test"
    assert isinstance(status["run_id"], str)


def test_export_failure_does_not_change_advisory_answer_or_leak_exception(tmp_path):
    class Broken(Client):
        def batch_ingest_runs(self, **kwargs):
            raise RuntimeError("private-error-canary")
    exporter = LangSmithExporter(settings_reader=lambda: Settings("fake-key"), client_factory=lambda _: Broken())
    answer, trace = respond("What is this app?", transport="browser", memory_store=MemoryStore(tmp_path / "memory.sqlite3"), trace_exporter=exporter)
    assert exporter.flush()
    assert trace["status"] == "help" and "CRA2" in answer
    assert exporter.status(trace) == {"status": "unavailable"}
    assert "private-error-canary" not in answer + json.dumps(trace)


@pytest.mark.parametrize("value", ["javascript:alert(1)", "https://evil.invalid/path", "https://smith.langchain.com.evil.invalid/path",
                                  "https://user:secret@smith.langchain.com/path", "https://smith.langchain.com:wrong/path",
                                  "https://smith.langchain.com/path)outside", "https://smith.langchain.com/\nsecret"])
def test_ui_link_allowlist(value):
    assert safe_url(value) is None


def test_langsmith_key_input_is_rejected_before_work(tmp_path, monkeypatch):
    secret = uuid4().hex
    monkeypatch.setenv("LANGSMITH_API_KEY", secret)
    def forbidden(*args, **kwargs):
        pytest.fail("No downstream work for credential input")
    answer, trace = respond(secret, transport="browser", retriever=forbidden, reviewer=forbidden, tool_runner=forbidden)
    assert trace["status"] == "unavailable" and secret not in answer + json.dumps(trace)


@pytest.mark.parametrize("status_code", [200, 401])
def test_real_sdk_ingestion_payload_and_swallowed_error_are_checked(status_code):
    import requests
    from requests.adapters import BaseAdapter
    from langsmith import Client as SDKClient
    from urllib3.util.retry import Retry
    captured = []
    class Adapter(BaseAdapter):
        def send(self, request, **kwargs):
            captured.append(request)
            reply = requests.Response()
            reply.status_code = status_code
            reply._content = b'{}'
            reply.headers['Content-Type'] = 'application/json'
            return reply
        def close(self):
            pass
    session = requests.Session()
    session.mount("https://", Adapter())
    failures = []
    canary_key = uuid4().hex
    sdk = SDKClient(api_url="https://api.smith.langchain.com", api_key=canary_key, session=session,
                    auto_batch_tracing=False, omit_traced_runtime_info=True, retry_config=Retry(total=0),
                    info={"batch_ingest_config": {"use_multipart_endpoint": False}},
                    tracing_error_callback=lambda _: failures.append(True))
    # The SDK mounts its retry adapter at construction; replace it afterwards.
    sdk.session.mount("https://", Adapter())
    try:
        checked = CheckedClient(sdk, failures)
        runs = build_runs(snapshot(), Settings(canary_key))
        if status_code == 200:
            checked.batch_ingest_runs(create=runs)
        else:
            with pytest.raises(ValueError, match="trace_ingestion_failed"):
                checked.batch_ingest_runs(create=runs)
    finally:
        sdk.close(timeout=1)
    assert captured
    bodies = b"\n".join(r.body if isinstance(r.body, bytes) else str(r.body).encode() for r in captured)
    assert b"canary" not in bodies and canary_key.encode() not in bodies
    assert b"memory_read" in bodies and b"recalled" in bodies
