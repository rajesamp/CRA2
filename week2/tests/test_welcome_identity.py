"""Verified identity, authenticated shared presence and real Gradio state isolation."""
import json
from types import SimpleNamespace

import gradio as gr
import httpx
import pytest
from fastapi.testclient import TestClient

from week2 import app, cloud_app
from week2.iap import IAPKeys, IAPSettings, IAPVerifier, Principal, mask_email
from week2.presence import Presence, principal_from_request
from week2.session_boundary import SessionBoundary, session_key
from week2.tests.test_cloud_storage import ObjectFixture, SERVICE
from week2.tests.test_iap import identity, token, AUDIENCE, OWNER


def test_welcome_example_passes_the_actual_admission_and_local_review(tmp_path):
    from week2.abuse import AbuseGate
    from week2.memory import MemoryStore
    from week2.owner_audit import OwnerAuditStore
    from week2.welcome import EXAMPLE
    from week4.telemetry import TelemetryStore
    gate = AbuseGate(store=OwnerAuditStore(tmp_path / "audit.sqlite3"))
    answer, _, trace = app.guarded_ui_reply(EXAMPLE, [], "Local evidence only", "welcome-example",
        gate=gate, client="synthetic-owner", memory_store=MemoryStore(tmp_path / "memory.sqlite3"),
        telemetry_store=TelemetryStore(tmp_path / "telemetry.sqlite3"))
    assert trace["status"] == "evidence_only" and "90%" in answer
    assert not trace["request_attempted"] and not trace["provider_used"]
    assert sum(event.get("event") == "tool_result" for event in trace["events"]) == 2


@pytest.mark.parametrize("email,masked", [
    ("rajan@example.test", "ra**an@example.test"), ("Abcdef@example.test", "ab**ef@example.test"),
    ("a@example.test", "a**@example.test"), ("ab@example.test", "a**@example.test"),
    ("abcd@example.test", "a**@example.test"),
])
def test_email_masking_does_not_reveal_the_complete_local_part(email, masked):
    assert mask_email(email) == masked
    assert email.casefold() != masked


def test_presence_is_shared_bounded_expires_and_escapes_html():
    now = [100.]
    registry = Presence(clock=lambda: now[0], capacity=2)
    owner = Principal("iap:" + "a" * 64, "ow**er@example.test", True)
    member = Principal("iap:" + "b" * 64, "<b>**@example.test", False)
    third = Principal("iap:" + "c" * 64, "th**rd@example.test", False)
    registry.touch(owner)
    member_view = registry.view(member)
    assert "ow**er" in member_view and "&lt;b&gt;" in member_view and "<b>" not in member_view
    assert "&lt;b&gt;" in registry.view(owner)
    registry.touch(third)
    assert len(registry.users) == 2
    now[0] += 301
    assert "&lt;b&gt;" not in registry.view(owner)
    assert len(registry.users) == 1
    assert not Presence().users  # Restart intentionally does not retain activity.


def test_identity_view_never_trusts_browser_username_or_email():
    for request in (None, SimpleNamespace(username=OWNER),
                    SimpleNamespace(username="iap:" + "a" * 64, email=OWNER)):
        with pytest.raises(ValueError):
            principal_from_request(request)


@pytest.mark.parametrize("emails", [("*",), ("not-an-email",), ["member@example.test"], ("x@example.test",) * 1001])
def test_allowlist_configuration_rejects_wildcards_and_invalid_entries(emails):
    with pytest.raises(ValueError):
        IAPSettings(AUDIENCE, OWNER, emails)


def test_real_mount_separates_two_invited_users_even_with_identical_browser_session(identity, tmp_path, monkeypatch):
    settings = IAPSettings(AUDIENCE, OWNER, ("member@example.test",))
    keys = IAPKeys(client=httpx.Client(transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json={"keys": [identity[1]]}))))
    verifier = IAPVerifier(settings, keys=keys)
    fixture = ObjectFixture(tmp_path / "objects.sqlite3")
    built = []
    def capture(**kwargs):
        demo = app.build_app(**kwargs)
        # A real mounted Gradio state round trip: an adversary reuses a known
        # browser session id and then the server's internal id.
        with demo:
            state = gr.State("")
            field = gr.Textbox()
            def private_note(value, saved):
                return value or saved, value or saved
            gr.Button().click(private_note, inputs=[field, state], outputs=[field, state],
                              api_name="private_note", api_visibility="private", queue=False)
        built.append(demo)
        return demo
    monkeypatch.setattr(cloud_app, "build_app", capture)
    protected = cloud_app.create_app(settings=settings, verifier=verifier, stores=fixture.stores())
    owner_token = token(identity)
    member_token = token(identity, email="member@example.test", sub="member-subject")
    owner, member = verifier.verify(owner_token), verifier.verify(member_token)
    headers = lambda signed: {"x-goog-iap-jwt-assertion": signed}
    with TestClient(protected) as client:
        for signed in (owner_token, member_token):
            config = client.get("/config", headers=headers(signed))
            assert config.status_code == 200
            assert OWNER not in config.text and "member@example.test" not in config.text
            assert config.headers["cache-control"] == "private, no-store"
        assert client.get("/", headers=headers(token(identity, email="outsider@example.test"))).status_code == 403

        def call(signed, name, data, session="reused-session"):
            return client.post("/gradio_api/run/" + name, headers=headers(signed),
                               json={"data": data, "session_hash": session})
        assert call(owner_token, "private_note", ["owner-private-canary", None]).status_code == 200
        result = call(member_token, "private_note", ["", None])
        assert result.status_code == 200 and result.json()["data"][0] == ""
        assert "owner-private-canary" not in result.text
        assert call(member_token, "private_note", ["", None], session_key(owner, "reused-session")).json()["data"][0] == ""
        assert call(owner_token, "private_note", ["", None]).json()["data"][0] == "owner-private-canary"
        own_view = call(owner_token, "show_identity", []).text
        member_view = call(member_token, "show_identity", []).text
        assert "ow**er@example.test" in own_view and "me**er@example.test" in own_view
        assert "ow**er@example.test" in member_view and "me**er@example.test" in member_view
        assert OWNER not in own_view and "member@example.test" not in own_view
        assert session_key(owner, "reused-session") in built[0].state_holder.session_data
        assert session_key(member, "reused-session") in built[0].state_holder.session_data

        # The new recovery callback runs through the real mount and admission
        # gate; one principal's declarations cannot become another's report.
        from week2.tests.test_incident_rollback import VALUES
        failed_values = list(VALUES); failed_values[4] = "Fail"
        owner_recovery = call(owner_token, "recovery", [*failed_values, None])
        assert owner_recovery.status_code == 200
        assert "Reported rollback blockers" in owner_recovery.json()["data"][0]
        member_recovery = call(member_token, "recovery", [*VALUES, {"forged": "activity-canary"}])
        assert member_recovery.status_code == 200
        assert "Recovery evidence is incomplete" in member_recovery.json()["data"][0]
        assert "Resolve reported blockers" not in member_recovery.json()["data"][0]
        assert "Request 1" in owner_recovery.json()["data"][2]
        assert "Request 1" in member_recovery.json()["data"][2]
        assert "activity-canary" not in member_recovery.text
        assert "NeMo / Retrieved context: Passed" in member_recovery.json()["data"][2]
        owner_again = call(owner_token, "recovery", [*VALUES, None])
        assert "Request 2" in owner_again.json()["data"][2]
        member_again = call(member_token, "clear_activity", [None])
        assert "No checks recorded" in member_again.json()["data"][1]
        owner_third = call(owner_token, "recovery", [*VALUES, None])
        assert "Request 3" in owner_third.json()["data"][2] and "Request 1" in owner_third.json()["data"][2]

        # Actual app memory callback with the two verified identities; the same
        # service name cannot make one user's preferences become another's.
        from inspect import unwrap
        reply = next(unwrap(fn.fn) for fn in built[0].fns.values() if fn.fn and fn.fn.__name__ == "reply")
        reply("Remember that checkout-service is always high-risk for our team.", [],
              "Local evidence only", "synthetic-session", [], SimpleNamespace(username=owner.key))
        assert fixture.stores().memory_for(owner.key).read(SERVICE)["high_risk"] is True
        assert fixture.stores().memory_for(member.key).read(SERVICE) is None


def test_session_protocol_namespaces_reads_writes_and_rejects_foreign_events():
    owner = Principal("iap:" + "a" * 64, "ow**er@example.test", True)
    member = Principal("iap:" + "b" * 64, "me**er@example.test", False)
    event = SimpleNamespace(username=owner.key, session_hash=session_key(owner, "browser"))
    demo = SimpleNamespace(_queue=SimpleNamespace(event_ids_to_events={"owner-event": event}))
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    async def inspect(scope, receive, send):
        request = Request(scope, receive)
        body = await request.json() if request.method == "POST" else None
        await JSONResponse({"path": scope["path"], "query": dict(request.query_params), "body": body})(scope, receive, send)
    boundary = SessionBoundary(inspect, demo, Presence())
    current = [owner]
    async def authenticated(scope, receive, send):
        scope.setdefault("state", {})["cra2_principal"] = current[0]
        await boundary(scope, receive, send)
    client = TestClient(authenticated)
    expected = session_key(owner, "browser")
    assert client.get("/gradio_api/heartbeat/browser").json()["path"].endswith(expected)
    assert client.get("/gradio_api/queue/data?session_hash=browser").json()["query"]["session_hash"] == expected
    assert client.post("/gradio_api/queue/join", json={"session_hash": "browser"}).json()["body"]["session_hash"] == expected
    assert client.post("/gradio_api/cancel", json={"session_hash": "browser", "event_id": "owner-event"}).status_code == 200
    current[0] = member
    assert client.post("/gradio_api/cancel", json={"session_hash": "browser", "event_id": "owner-event"}).status_code == 403
    for path in ("/call/private_note/owner-event", "/stream/owner-event", "/component_server", "/upload", "/deep_link?session_hash=browser", "/file=private.json", "/future_unknown_api"):
        for method in (client.get, client.post):
            assert method("/gradio_api" + path).status_code == 403
    for data in ({}, {"session_hash": "../other"}, {"session_hash": ["browser"]},
                 {"session_hash": "browser", "event_id": "owner-event"}):
        assert client.post("/gradio_api/queue/join", json=data).status_code == 400
    assert client.post("/gradio_api/queue/join", content="x" * (256 * 1024 + 1)).status_code == 413
    assert client.get("/gradio_api/queue/data?session_hash=a&session_hash=b").status_code == 400
