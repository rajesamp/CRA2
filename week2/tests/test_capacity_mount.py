"""Queue contract for the actual CRA2 Gradio callback inventory."""
from inspect import unwrap

import httpx
import pytest
from fastapi.testclient import TestClient

from week2 import app, cloud_app
from week2.app import build_app
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
