"""Exercise the staging rehearsal with signed test identities and a local Firestore emulator."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
import os
import re
from threading import Barrier

from fastapi.testclient import TestClient
import httpx
import pytest

from invitations.staging.app import COOKIE, create_app
from invitations.staging.firestore_sessions import FirestoreSessions
from invitations.staging.rehearsal import create_rehearsal_app, from_env as rehearsal_from_env
from invitations.staging.rehearsal_store import OTHER_APPLICANT, RECIPIENT, Rehearsals
from test_staging_firestore import COOKIE_HOST, DATABASE, project
from test_staging_identity import ORIGIN, PIN, SETTINGS, keysets, login, provider, run_staging_browser


@pytest.fixture
def pilot(project, provider):
    @contextmanager
    def connect(*, cookie=None):
        sessions = FirestoreSessions.connect(project, DATABASE)
        sessions.clock = lambda: provider.now
        store = Rehearsals(sessions.client, clock=lambda: provider.now)
        app = create_rehearsal_app(
            SETTINGS, sessions, store,
            transport=httpx.MockTransport(provider.http), key_clock=lambda: provider.now,
        )
        try:
            with TestClient(
                app, base_url=ORIGIN, follow_redirects=False,
                headers={"x-goog-iap-jwt-assertion": provider.assertion(), "Origin": ORIGIN},
            ) as browser:
                if cookie:
                    browser.cookies.set(COOKIE, cookie, domain=COOKIE_HOST)
                yield browser, store
        finally:
            sessions.client.close()
    return connect


def open_case(browser):
    index = browser.get("/rehearsal")
    assert index.status_code == 200
    request = re.search(r'action="(/rehearsal/[\w-]+/request)"', index.text).group(1)
    response = browser.post(request)
    assert response.status_code == 303
    return response.headers["location"]


def send(browser, path):
    assert browser.post(path + "/approve").status_code == 303
    approved = browser.get(path)
    assert "Synthetic deliveries: 0" in approved.text
    assert "Synthetic mailbox" not in approved.text
    assert browser.post(path + "/send").status_code == 303
    rendered = browser.get(path)
    assert rendered.headers["cache-control"] == "no-store"
    assert "Synthetic deliveries: 1" in rendered.text
    assert "Real deliveries: 0 · External grants: 0" in rendered.text
    return re.search(r"<code>([\w-]{32})</code>", rendered.text).group(1)


def redeem(browser, path, code, actor=RECIPIENT):
    return browser.post(path + "/redeem", data={"actor": actor, "code": code})


def recipient(path, actor=RECIPIENT):
    return f"{path}/workspace/{actor}"


def record(store, path):
    return store.read(PIN, SETTINGS.scope_key, path.rsplit("/", 1)[1])


def test_owner_rehearsal_survives_restart_and_revocation(pilot, provider):
    with pilot() as (before, _):
        assert before.get("/rehearsal").status_code == 403
        assert login(before, provider).status_code == 303
        assert "Open synthetic invitation rehearsal" in before.get("/").text
        cookie = before.cookies[COOKIE]
        path = open_case(before)
        assert before.post(path + "/send").status_code == 409
        code = send(before, path)
    provider.now += 30
    with pilot(cookie=cookie) as (after, store):
        original = record(store, path)
        assert after.post(path + "/request").status_code == 303
        assert after.post(path + "/send").status_code == 303
        assert original == record(store, path)
        assert (original["redeem_by"] - original["sent_at"]).total_seconds() == 600
        assert after.get(recipient(path)).status_code == 403
        assert redeem(after, path, code, OTHER_APPLICANT).status_code == 409
        assert redeem(after, path, code, "external@example.test").status_code == 409
        assert redeem(after, path, code, RECIPIENT).status_code == 303
        assert redeem(after, path, code).status_code == 409
        assert code not in after.get(path).text
        assert after.get(recipient(path)).status_code == 200
        assert after.get(recipient(path, OTHER_APPLICANT)).status_code == 403
    with pilot(cookie=cookie) as (restarted, store):
        assert restarted.get(recipient(path)).status_code == 200
        assert restarted.post(path + "/revoke").status_code == 303
        assert restarted.post(path + "/revoke").status_code == 303
        assert restarted.get(recipient(path)).status_code == 403
        assert redeem(restarted, path, code).status_code == 409
        assert record(store, path)["receipt_id"] == original["receipt_id"]
    with pilot(cookie=cookie) as (later, _):
        assert later.get(recipient(path)).status_code == 403


def test_expiry_starts_at_receipt_and_is_exact(pilot, provider):
    with pilot() as (browser, store):
        assert login(browser, provider).status_code == 303
        expiring_case = open_case(browser)
        expiring_code = send(browser, expiring_case)
        provider.now += 1
        active_case = open_case(browser)
        active_code = send(browser, active_case)
        provider.now += 599
        assert redeem(browser, expiring_case, expiring_code).status_code == 409
        assert "expired" in browser.get(expiring_case).text
        assert expiring_code not in browser.get(expiring_case).text
        original = record(store, expiring_case)
        assert browser.post(expiring_case + "/send").status_code == 303
        assert original == record(store, expiring_case)
        assert redeem(browser, active_case, active_code).status_code == 303


def test_concurrent_send_and_redemption_have_one_effect(pilot, provider):
    with pilot() as (browser, _):
        assert login(browser, provider).status_code == 303
        cookie = browser.cookies[COOKIE]
        path = open_case(browser)
        assert browser.post(path + "/approve").status_code == 303

    def race(operation):
        barrier = Barrier(2, timeout=10)

        def invoke(_):
            with pilot(cookie=cookie) as (browser, _):
                barrier.wait()
                return operation(browser).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            return sorted(pool.map(invoke, range(2)))

    assert race(lambda b: b.post(path + "/send")) == [303, 303]
    with pilot(cookie=cookie) as (browser, store):
        rendered = browser.get(path)
        assert "Synthetic deliveries: 1" in rendered.text
        original = record(store, path)
        code = original["mailbox_code"]
    assert race(lambda b: redeem(b, path, code)) == [303, 409]
    with pilot(cookie=cookie) as (browser, store):
        saved = record(store, path)
        assert saved["phase"] == "redeemed"
        assert saved["receipt_id"] == original["receipt_id"]
        assert "mailbox_code" not in saved
        assert browser.get(recipient(path)).status_code == 200


def test_owner_proof_and_origin_are_required_on_every_route(pilot, provider):
    with pilot() as (browser, _):
        assert login(browser, provider).status_code == 303
        path = open_case(browser)
        code = send(browser, path)
        assert browser.post(path + "/revoke", headers={"Origin": "https://other.example.test"}).status_code == 403
        assert browser.post(path + "/redeem", content="x" * 1025,
                            headers={"Content-Type": "application/x-www-form-urlencoded"}).status_code == 413
        browser.headers["x-goog-iap-jwt-assertion"] = provider.assertion(sub="accounts.google.com:other")
        assert browser.get(path).status_code == 403
        assert redeem(browser, path, code).status_code == 403
        browser.headers["x-goog-iap-jwt-assertion"] = provider.assertion()
        assert browser.post("/auth/logout").status_code == 303
        assert browser.get("/rehearsal").status_code == 403
        assert browser.get(path).status_code == 403
        assert browser.get(recipient(path)).status_code == 403
        assert browser.post(path + "/approve").status_code == 403
        assert browser.post(path + "/send").status_code == 403
        assert redeem(browser, path, code).status_code == 403
        assert browser.post(path + "/revoke").status_code == 403


def test_identity_only_app_has_no_rehearsal_routes(tmp_path, provider):
    from invitations.staging.sessions import Sessions

    sessions = Sessions(tmp_path / "private")
    config = replace(SETTINGS, mode="verify-only", owner_pin=None)
    with pytest.raises(ValueError, match="enrolled"):
        create_rehearsal_app(config, sessions, None)
    app = create_app(SETTINGS, sessions, transport=httpx.MockTransport(provider.http))
    with TestClient(app, base_url=ORIGIN) as browser:
        assert browser.get("/rehearsal").status_code == 404


def test_rehearsal_entrypoint_requires_durable_owner_enrollment(monkeypatch, tmp_path, project):
    values = {
        "ORIGIN": SETTINGS.origin,
        "IAP_AUDIENCE": SETTINGS.audience,
        "CLIENT_ID": SETTINGS.client_id,
        "CLIENT_SECRET": SETTINGS.client_secret,
        "OWNER_EMAIL": SETTINGS.owner_email,
        "MODE": "verify-only",
        "STATE_DIR": str(tmp_path / "private"),
    }
    for name in ("OWNER_PIN", "FIRESTORE_PROJECT", "FIRESTORE_DATABASE"):
        monkeypatch.delenv("INVITATION_STAGE_" + name, raising=False)
    monkeypatch.delenv("K_SERVICE", raising=False)
    for name, value in values.items():
        monkeypatch.setenv("INVITATION_STAGE_" + name, value)
    with pytest.raises(ValueError, match="enrolled"):
        rehearsal_from_env()

    monkeypatch.setenv("INVITATION_STAGE_MODE", "enrolled")
    monkeypatch.setenv("INVITATION_STAGE_OWNER_PIN", PIN)
    with pytest.raises(ValueError, match="durable"):
        rehearsal_from_env()
    monkeypatch.delenv("INVITATION_STAGE_STATE_DIR")
    monkeypatch.setenv("INVITATION_STAGE_FIRESTORE_PROJECT", project)
    monkeypatch.setenv("INVITATION_STAGE_FIRESTORE_DATABASE", DATABASE)
    with TestClient(rehearsal_from_env(), base_url=ORIGIN) as browser:
        assert browser.get("/healthz").json() == {"status": "ok"}
        assert browser.get("/rehearsal").status_code == 403


@pytest.mark.skipif(
    os.environ.get("INVITATION_BROWSER") != "1", reason="opt-in installed Chrome/Playwright probe"
)
def test_owner_rehearsal_in_chrome(tmp_path, provider, project):
    sessions = FirestoreSessions.connect(project, DATABASE)
    try:
        store = Rehearsals(sessions.client)
        run_staging_browser(
            tmp_path, provider, lambda settings: create_rehearsal_app(
                settings, sessions, store, transport=httpx.MockTransport(provider.http),
            ), "--rehearsal",
        )
    finally:
        sessions.client.close()
