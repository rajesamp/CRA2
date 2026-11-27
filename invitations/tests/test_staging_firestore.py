"""Run against a loopback Firestore emulator with synthetic Google and IAP proofs."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import os
import subprocess
import sys
from threading import Barrier
from urllib.parse import urlsplit
from uuid import uuid4

import pytest

from invitations.staging.firestore_sessions import FirestoreSessions
from invitations.staging.google import Denied, TOKEN_ENDPOINT
from invitations.staging.sessions import session_store_from_env
from test_staging_identity import COOKIE, PIN, SETTINGS, callback, client, keysets, login, provider, start

DATABASE = "identity-test-staging"
COOKIE_HOST = urlsplit(SETTINGS.origin).hostname


@pytest.fixture
def project():
    host = os.environ.get("FIRESTORE_EMULATOR_HOST", "")
    if not host:
        pytest.skip("Firestore emulator not configured")
    assert host.split(":")[0] == "127.0.0.1", "Use a loopback Firestore emulator"
    return f"demo-cra2-{uuid4().hex[:8]}"


@pytest.fixture
def store(project, provider):
    def new():
        instance = FirestoreSessions.connect(project, DATABASE)
        instance.clock = lambda: provider.now
        return instance

    return new


def test_cloud_run_refuses_ephemeral_or_ambiguous_configuration(monkeypatch, tmp_path):
    for name in ("STATE_DIR", "FIRESTORE_PROJECT", "FIRESTORE_DATABASE"):
        monkeypatch.delenv("INVITATION_STAGE_" + name, raising=False)
    monkeypatch.setenv("K_SERVICE", "identity-test-staging")
    monkeypatch.delenv("FIRESTORE_EMULATOR_HOST", raising=False)
    with pytest.raises(ValueError):
        session_store_from_env()
    monkeypatch.setenv("INVITATION_STAGE_STATE_DIR", str(tmp_path))
    with pytest.raises(ValueError):
        session_store_from_env()
    monkeypatch.delenv("INVITATION_STAGE_STATE_DIR")
    monkeypatch.setenv("INVITATION_STAGE_FIRESTORE_PROJECT", "demo-local")
    monkeypatch.setenv("INVITATION_STAGE_FIRESTORE_DATABASE", "(default)")
    with pytest.raises(ValueError):
        session_store_from_env()
    monkeypatch.setenv("INVITATION_STAGE_FIRESTORE_DATABASE", "identity-test")
    with pytest.raises(ValueError):
        session_store_from_env()
    monkeypatch.setenv("INVITATION_STAGE_FIRESTORE_DATABASE", DATABASE)
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8791")
    with pytest.raises(ValueError):
        session_store_from_env()


def test_restarts_across_processes(project):
    env = {
        **os.environ,
        "INVITATION_STAGE_FIRESTORE_PROJECT": project,
        "INVITATION_STAGE_FIRESTORE_DATABASE": DATABASE,
    }
    env.pop("INVITATION_STAGE_STATE_DIR", None)
    prelude = (
        "import json,sys; "
        "from invitations.staging.sessions import session_store_from_env; "
        "store=session_store_from_env(); "
    )

    def run(code, data=None):
        result = subprocess.run(
            [sys.executable, "-c", prelude + code],
            input=json.dumps(data), env=env, capture_output=True, text=True, timeout=20, check=True,
        )
        return json.loads(result.stdout)

    pending = run("sid,attempt=store.start('', 'synthetic-owner', 'test-scope'); print(json.dumps([sid,attempt.state]))")
    bound = run(
        "sid,state=json.load(sys.stdin); store.consume(sid,state,'synthetic-owner','test-scope'); "
        "print(json.dumps(store.establish(sid,'synthetic-owner','test-scope')))",
        pending,
    )
    assert bound != pending[0]
    assert run(
        "sid=json.load(sys.stdin); print(json.dumps(store.bound(sid,'synthetic-owner','test-scope')))", bound,
    ) is True


def test_http_callback_and_logout_survive_app_restart(store, provider):
    with client(SETTINGS, store(), provider) as before:
        params = provider.issue(start(before))
        pending = before.cookies[COOKIE]
    with client(SETTINGS, store(), provider) as after:
        after.cookies.set(COOKIE, pending, domain=COOKIE_HOST)
        assert callback(after, params).status_code == 303
        established = after.cookies[COOKIE]
        assert established != pending
    with client(SETTINGS, store(), provider) as restarted:
        restarted.cookies.set(COOKIE, established, domain=COOKIE_HOST)
        assert restarted.get("/owner").json() == {"owner_verified": True}
        assert restarted.post("/auth/logout").status_code == 303
    assert not store().bound(established, PIN, SETTINGS.scope_key)


def test_expiry_is_immediate_even_if_emulator_has_not_deleted_records(store, provider):
    with client(SETTINGS, store(), provider) as first:
        params = provider.issue(start(first))
        pending = first.cookies[COOKIE]
    provider.now += 300
    with client(SETTINGS, store(), provider) as second:
        second.cookies.set(COOKIE, pending, domain=COOKIE_HOST)
        assert callback(second, params).status_code == 403
        assert TOKEN_ENDPOINT not in provider.calls
        assert store()._ref(pending).get(timeout=5).exists
        second.cookies.clear()
        assert login(second, provider).status_code == 303
        established = second.cookies[COOKIE]
    provider.now += 899
    assert store().bound(established, PIN, SETTINGS.scope_key)
    provider.now += 1
    assert not store().bound(established, PIN, SETTINGS.scope_key)
    assert store()._ref(established).get(timeout=5).exists


def test_callback_race_and_replay_use_one_token_exchange(store, provider):
    with client(SETTINGS, store(), provider) as before:
        params = provider.issue(start(before))
        pending = before.cookies[COOKIE]

    ready = Barrier(2, timeout=10)

    def attempt():
        database = store()
        read = database._read

        def read_pending_together(document):
            snapshot = read(document)
            if snapshot.exists and snapshot.get("phase") == "pending":
                ready.wait()
            return snapshot

        database._read = read_pending_together
        with client(SETTINGS, database, provider) as browser:
            browser.cookies.set(COOKIE, pending, domain=COOKIE_HOST)
            return callback(browser, params).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: attempt(), range(2))) == [303, 403]
    with client(SETTINGS, store(), provider) as restarted:
        restarted.cookies.set(COOKIE, pending, domain=COOKIE_HOST)
        assert callback(restarted, params).status_code == 403
    assert provider.calls.count(TOKEN_ENDPOINT) == 1


def test_interrupted_claim_cannot_replay_and_expired_claim_cannot_bind(store, provider):
    with client(SETTINGS, store(), provider) as before:
        params = provider.issue(start(before))
        pending = before.cookies[COOKIE]
    database = store()
    database.consume(pending, params["state"], PIN, SETTINGS.scope_key)
    claimed = database._ref(pending).get(timeout=5).to_dict()
    assert claimed["phase"] == "exchanging"
    assert not {"state", "nonce", "verifier"} & claimed.keys()
    with client(SETTINGS, store(), provider) as restarted:
        restarted.cookies.set(COOKIE, pending, domain=COOKIE_HOST)
        assert callback(restarted, params).status_code == 403
        assert restarted.get("/owner").status_code == 403
        assert TOKEN_ENDPOINT not in provider.calls
    provider.now += 300
    with pytest.raises(Denied):
        store().establish(pending, PIN, SETTINGS.scope_key)
    with client(SETTINGS, store(), provider) as fresh:
        assert login(fresh, provider).status_code == 303


def test_enrollment_reads_only_one_active_bound_principal(store, provider):
    settings = replace(SETTINGS, mode="verify-only", owner_pin=None)
    with client(settings, store(), provider) as browser:
        params = provider.issue(start(browser))
        with pytest.raises(ValueError):
            store().candidate(settings)
        assert callback(browser, params).status_code == 303
        assert store().candidate(settings) == PIN
        assert browser.get("/owner").status_code == 403
    with client(settings, store(), provider) as other:
        other.headers["x-goog-iap-jwt-assertion"] = provider.assertion(sub="accounts.google.com:other")
        assert login(other, provider, sub="other").status_code == 303
    with pytest.raises(ValueError):
        store().candidate(settings)
    provider.now += 900
    with pytest.raises(ValueError):
        store().candidate(settings)
