"""Exercise saturation, worker lifetime and delivery through the signed Gradio mount."""
import asyncio
from contextlib import contextmanager
from threading import Event
from time import monotonic, sleep
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.requests import ClientDisconnect

from week2 import app, capacity, session_boundary
from week2.capacity import LocalCapacity
from week2.cloud_app import create_app
from week2.iap import IAPKeys, IAPSettings, IAPVerifier
from week2.tests.test_capacity_mount import owner_mount
from week2.tests.test_cloud_storage import ObjectFixture
from week2.tests.test_iap import AUDIENCE, OWNER, identity, token
from week2.tests.test_incident_rollback import VALUES


def recovery_id(client, headers):
    config = client.get("/config", headers=headers).json()
    return next(binding["id"] for binding in config["dependencies"] if binding["api_name"] == "recovery")


def join(client, headers, callback, session):
    fields = list(VALUES)
    fields[2] = "Proposed compatible update " + session
    return client.post("/gradio_api/queue/join", headers=headers,
                       json={"session_hash": session, "fn_index": callback, "data": [*fields, None]})


def stream(client, headers, session):
    response = client.get("/gradio_api/queue/data", headers=headers, params={"session_hash": session})
    assert response.status_code == 200
    return response.text


@contextmanager
def hold_first_worker(monkeypatch):
    started, release = Event(), Event()
    calls = []
    original = app.guarded_analyze
    def analyze(values, **kwargs):
        calls.append(values[2])
        if len(calls) == 1:
            started.set()
            assert release.wait(10)
        return original(values, **kwargs)
    monkeypatch.setattr(app, "guarded_analyze", analyze)
    try:
        yield started, calls
    finally:
        release.set()


def test_burst_cancel_and_owner_status(owner_mount, monkeypatch):
    client, headers, path = owner_mount
    callback = recovery_id(client, headers)
    with hold_first_worker(monkeypatch) as (started, calls):
        assert join(client, headers, callback, "one").status_code == 200 and started.wait(5)
        second = join(client, headers, callback, "two")
        assert second.status_code == 200
        assert join(client, headers, callback, "three").status_code == 429
        assert client.get("/config", headers=headers).status_code == 200
        response = client.post("/gradio_api/cancel", headers=headers, json={
            "session_hash": "two", "event_id": second.json()["event_id"], "fn_index": callback})
        assert response.status_code == 200
        with LocalCapacity(path).transaction() as db:
            assert dict(db.execute("SELECT state, COUNT(*) FROM reviews GROUP BY state")) == {"running": 1, "cancelled": 1}
        assert len(calls) == 1
    assert '"success":true' in stream(client, headers, "one")


def test_expired_queued_worker_suppresses_result_and_holds_slot(owner_mount, monkeypatch):
    client, headers, path = owner_mount
    callback = recovery_id(client, headers)
    monkeypatch.setattr(capacity, "RUN_SECONDS", 0.25)
    store = LocalCapacity(path)
    with hold_first_worker(monkeypatch) as (started, _):
        assert join(client, headers, callback, "slow").status_code == 200 and started.wait(5)
        result = stream(client, headers, "slow")
        assert '"retry_after":1' in result and '"success":false' in result
        assert "Analysis only" not in result
        with store.transaction() as db:
            assert db.execute("SELECT state, stop_reason FROM reviews").fetchone() == ("running", "expired")
    until = monotonic() + 6
    while monotonic() < until:
        with store.transaction() as db:
            if db.execute("SELECT state FROM reviews").fetchone() == ("expired",):
                return
        sleep(0.05)
    pytest.fail("Worker failed to release its slot after returning")


def test_direct_delivery_receipt_repeats_once(owner_mount):
    client, headers, path = owner_mount
    body = {"session_hash": "direct", "data": [*VALUES, None]}
    delivery = {**headers, "idempotency-key": uuid4().hex}
    first = client.post("/gradio_api/run/recovery", headers=delivery, json=body)
    assert first.status_code == 200
    replay = client.post("/gradio_api/api/recovery", headers=delivery, json=body)
    assert replay.status_code == 202
    assert replay.json() == {"receipt": first.headers["x-review-receipt"], "state": "completed"}
    another = client.post("/gradio_api/run/recovery", headers={**headers, "idempotency-key": uuid4().hex}, json=body)
    assert another.status_code == 200
    with LocalCapacity(path).transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM reviews").fetchone() == (2,)


def test_waiting_review_expires_before_entering_the_callback(owner_mount, monkeypatch):
    client, headers, path = owner_mount
    callback = recovery_id(client, headers)
    monkeypatch.setattr(capacity, "WAIT_SECONDS", 0.35)
    monkeypatch.setattr(session_boundary, "WAIT_SECONDS", 0.35)
    with hold_first_worker(monkeypatch) as (started, calls):
        assert join(client, headers, callback, "first").status_code == 200 and started.wait(5)
        assert join(client, headers, callback, "waiting").status_code == 200
        result = stream(client, headers, "waiting")
        assert '"retry_after":1' in result and '"success":false' in result
        assert len(calls) == 1
        with LocalCapacity(path).transaction() as db:
            assert dict(db.execute("SELECT state, COUNT(*) FROM reviews GROUP BY state")) == {"running": 1, "expired": 1}
    assert '"success":true' in stream(client, headers, "first")


def test_unavailable_ledger_returns_503_without_a_downstream_call(owner_mount, monkeypatch):
    client, headers, path = owner_mount
    callback = recovery_id(client, headers)
    path.parent.mkdir(exist_ok=True, mode=0o700)
    path.write_bytes(b"Unavailable synthetic test fixture")
    path.chmod(0o600)
    monkeypatch.setattr(app, "guarded_analyze", lambda *a, **kw: pytest.fail("Refusal reached a reviewer"))
    response = join(client, headers, callback, "unavailable")
    assert response.status_code == 503 and response.headers["retry-after"] == "1"
    assert "fixture" not in response.text


def test_mount_burst_with_two_signed_reviewers_preserves_fifo_and_refusal(tmp_path, identity, monkeypatch):
    keys = IAPKeys(client=httpx.Client(transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json={"keys": [identity[1]]}))))
    member = "second@example.test"
    settings = IAPSettings(AUDIENCE, OWNER, (member,))
    path = tmp_path / "private" / "capacity.db"
    protected = create_app(settings=settings, verifier=IAPVerifier(settings, keys=keys),
                           stores=ObjectFixture(tmp_path / "objects.db").stores(), local_capacity_path=path)
    owner, peer = ({"x-goog-iap-jwt-assertion": token(identity, email=email, sub=subject)}
                   for email, subject in ((OWNER, "owner-fixture"), (member, "peer-fixture")))
    with TestClient(protected) as client:
        callback = recovery_id(client, owner)
        with hold_first_worker(monkeypatch) as (started, calls):
            assert join(client, owner, callback, "a").status_code == 200 and started.wait(5)
            assert join(client, peer, callback, "b").status_code == 200
            assert join(client, peer, callback, "c").status_code == 200
            busy = join(client, owner, callback, "d")
            assert busy.status_code == 503 and busy.headers["retry-after"] == "1"
            assert len(calls) == 1
            with LocalCapacity(path).transaction() as db:
                assert dict(db.execute("SELECT state, COUNT(*) FROM reviews GROUP BY state")) == {"running": 1, "waiting": 2}
        for headers, session in ((owner, "a"), (peer, "b"), (peer, "c")):
            assert '"success":true' in stream(client, headers, session)
        assert calls == ["Proposed compatible update " + label for label in ("a", "b", "c")]


def test_disconnected_data_stream_reattaches_to_same_owned_event(owner_mount, monkeypatch):
    client, headers, path = owner_mount
    callback = recovery_id(client, headers)
    async def drop_after_first_frame():
        scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
                 "method": "GET", "scheme": "http", "http_version": "1.1", "path": "/gradio_api/queue/data",
                 "query_string": b"session_hash=rejoin", "headers": [(k.encode(), v.encode()) for k, v in headers.items()]}
        async def receive():
            await asyncio.Event().wait()
        async def send(message):
            if message["type"] == "http.response.body":
                raise OSError("Synthetic browser disconnected")
        with pytest.raises(ClientDisconnect):
            await client.app(scope, receive, send)
    with hold_first_worker(monkeypatch) as (started, _):
        response = join(client, headers, callback, "rejoin")
        assert response.status_code == 200 and started.wait(5)
        client.portal.call(drop_after_first_frame)
    result = stream(client, headers, "rejoin")
    assert response.json()["event_id"] in result and '"success":true' in result
    with LocalCapacity(path).transaction() as db:
        assert list(db.execute("SELECT state FROM reviews")) == [("completed",)]
