"""Queue contract for the actual CRA2 Gradio callback inventory."""
from inspect import unwrap
import asyncio
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from week2 import app, cloud_app
from week2.app import build_app
from week2.capacity import Busy, LocalCapacity
from week2.capacity_streams import CapacityStreams
from week2.iap import IAPKeys, IAPSettings, IAPVerifier
from week2.tests.test_cloud_storage import ObjectFixture
from week2.tests.test_iap import AUDIENCE, OWNER, identity, token
from week2.tests.test_incident_rollback import VALUES


@pytest.fixture(scope="module")
def demo():
    return build_app()


def test_review_queue_has_a_finite_waiting_room(demo):
    assert demo._queue.max_size == 2


def test_all_review_callbacks_share_one_running_slot(demo):
    reviews = [
        fn for fn in demo.fns.values()
        if fn.fn and unwrap(fn.fn).__name__ in {"reply", "recovery"}
    ]
    # submit, retry and option selection use three bindings of the chat wrapper.
    # The named API and recovery each register another work-bearing callback.
    assert sorted(fn.name for fn in reviews) == ["_submit_fn"] * 3 + ["recovery", "reply"]
    assert len({fn.concurrency_id for fn in reviews}) == 1
    assert all(fn.queue and fn.concurrency_limit == 1 for fn in reviews)


@pytest.fixture
def owner_mount(identity, tmp_path):
    settings = IAPSettings(AUDIENCE, OWNER)
    keys = IAPKeys(client=httpx.Client(transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json={"keys": [identity[1]]}))))
    verifier = IAPVerifier(settings, keys=keys)
    stores = ObjectFixture(tmp_path / "objects.db").stores()
    path = tmp_path / "private" / "capacity.db"
    mounted = cloud_app.create_app(settings=settings, verifier=verifier, stores=stores, local_capacity_path=path)
    with TestClient(mounted) as client:
        yield client, {"x-goog-iap-jwt-assertion": token(identity)}, path


def test_direct_recovery_quota_shared_across_tabs_at_the_authenticated_mount(owner_mount, monkeypatch):
    client, headers, path = owner_mount
    calls = []
    analyze = app.guarded_analyze
    def counted(*args, **kwargs):
        calls.append(1)
        return analyze(*args, **kwargs)
    monkeypatch.setattr(app, "guarded_analyze", counted)
    body = {"data": [*VALUES, None], "session_hash": "a"}
    assert client.post("/gradio_api/run/recovery", json=body).status_code == 401
    assert not path.exists()
    for index in range(4):
        body["session_hash"] = f"tab{index}"
        response = client.post("/gradio_api/run/recovery", headers=headers, json=body)
        assert response.status_code == 200
    busy = client.post("/gradio_api/api/recovery", headers=headers, json=body)
    assert busy.status_code == 429 and 1 <= int(busy.headers["Retry-After"]) <= 60
    assert len(calls) == 4
    assert client.post("/gradio_api/run/show_identity", headers=headers,
                       json={"data": [], "session_hash": "a"}).status_code == 200


def test_queued_chat_and_recovery_share_the_direct_call_budget(owner_mount):
    client, headers, path = owner_mount
    config = client.get("/config", headers=headers).json()
    ids = {fn["api_name"]: fn["id"] for fn in config["dependencies"]}
    assert {"submit_review", "retry_review", "choose_review", "ui_response", "recovery"} <= ids.keys()
    ledger = LocalCapacity(path)
    chat = ["What is this app?", [], None, None, None, None]
    for number, (name, inputs) in enumerate((("submit_review", chat), ("recovery", [*VALUES, None]))):
        session = "queue" + str(number)
        wrapped = [{"cra2_delivery": uuid4().hex, "value": inputs[0]}, *inputs[1:]]
        submission = {"session_hash": session, "fn_index": ids[name], "data": wrapped}
        response = client.post("/gradio_api/queue/join", headers=headers, json=submission)
        assert response.status_code == 200, response.text
        replay = client.post("/gradio_api/queue/join", headers=headers, json=submission)
        assert replay.status_code == 200 and response.json() == replay.json()
        stream = client.get("/gradio_api/queue/data", headers=headers, params={"session_hash": session})
        assert response.json()["event_id"] in stream.text
        assert "process_completed" in stream.text and '"success":true' in stream.text.replace(" ", "")
    with ledger.transaction() as db:
        assert list(db.execute("SELECT operation, state FROM reviews ORDER BY rowid")) == [
            ("chat", "completed"), ("recovery", "completed")]
    for _ in range(2):
        assert client.post("/gradio_api/run/recovery", headers=headers,
                           json={"session_hash": "direct", "data": [*VALUES, None]}).status_code == 200
    busy = client.post("/gradio_api/queue/join", headers=headers,
                       json={"session_hash": "retry", "fn_index": ids["retry_review"], "data": [[], None, None, None, None]})
    assert busy.status_code == 429 and "Retry-After" in busy.headers


def test_combined_connection_ceiling_leaves_owner_status_available(owner_mount):
    client, headers, _ = owner_mount
    boundary = client.app.app
    slots = boundary.streams
    slots.acquire("fixture", "active-tab", "heartbeat")
    slots.acquire("fixture", "active-tab", "data")
    try:
        response = client.get("/gradio_api/heartbeat/another-tab", headers=headers)
        assert response.status_code == 503 and response.headers["retry-after"] == "1"
        assert client.get("/config", headers=headers).status_code == 200
    finally:
        slots.release("active-tab", "heartbeat", finished=True)
        slots.release("active-tab", "data", finished=True)
    assert not slots.active and slots.maximum == 2


def test_reconnect_budget_idle_clock_and_abandoned_event(tmp_path):
    async def exercise():
        clock = [100.0]
        store = LocalCapacity(tmp_path / "private" / "reviews.db")
        receipt = store.reserve("client", "session", "chat")
        store.accept(receipt, "event")
        removed = []
        async def clean_events(*, event_id):
            removed.append(event_id)
        queue = SimpleNamespace(pending_event_ids_session={"session": {"event"}},
                                pending_messages_per_session={"session": object()}, clean_events=clean_events)
        streams = CapacityStreams(SimpleNamespace(_queue=queue), store, clock=lambda: clock[0])
        for _ in range(5):
            streams.acquire("client", "session", "data")
            streams.release("session", "data", finished=False)
        with pytest.raises(Busy) as busy:
            streams.acquire("client", "session", "data")
        assert busy.value.status == 429 and busy.value.retry_after == 60
        assert len(streams.orphans) == 1 and not removed
        streams.orphans["session"].cancel()
        streams._start_cleanup("session")
        await asyncio.gather(*streams.tasks)
        assert removed == ["event"] and not store.session_work("session")
        clock[0] += 60
        streams.acquire("client", "session", "heartbeat")
        clock[0] += 59.9
        assert await streams.idle_time_left("session") > 0
        clock[0] += 0.1
        assert await streams.idle_time_left("session") == 0
        streams.release("session", "heartbeat", finished=True)
    asyncio.run(exercise())
