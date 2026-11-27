"""Drive the local staging application with two independently signed identity proofs."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import base64
import hashlib
import json
import os
import socket
import subprocess
import sys
import threading
from html import escape
import time
from urllib.parse import parse_qs, urlencode, urlsplit

from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi.testclient import TestClient
import httpx
import jwt
import pytest
import uvicorn
from starlette.responses import HTMLResponse

from invitations.staging.__main__ import main as candidate_command
from invitations.staging.app import COOKIE, create_app, from_env
from invitations.staging.google import (
    AUTHORIZATION,
    GOOGLE_KEYS,
    IAP_ISSUER,
    IAP_KEYS,
    TOKEN_ENDPOINT,
    Denied,
    Settings,
    principal_key,
)
from invitations.staging.sessions import Sessions, enrollment_candidate

ORIGIN = "https://staging.example.test"
EMAIL = "owner@example.test"
CLIENT = "local-stage.apps.googleusercontent.com"
AUD = "/projects/123456789/locations/us-west1/services/cra2-invitations-staging"
SUB = "0123456789"
PIN = "iap:" + hashlib.sha256((IAP_ISSUER + "\0accounts.google.com:" + SUB).encode()).hexdigest()
SETTINGS = Settings(ORIGIN, AUD, CLIENT, "synthetic-secret", EMAIL, "enrolled", PIN)


def query(url):
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}


@pytest.fixture(scope="module")
def keysets():
    return {
        "iap": [ec.generate_private_key(ec.SECP256R1()) for _ in range(2)],
        "oidc": [rsa.generate_private_key(public_exponent=65537, key_size=2048) for _ in range(2)],
    }


class Providers:
    def __init__(self, keysets):
        self.keysets = keysets
        self.index = {"iap": 0, "oidc": 0}
        self.outage = set()
        self.calls = []
        self.codes = {}
        self.oidc_token = None
        self.callback = SETTINGS.callback
        self.now = 1000.0

    def sign(self, kind, claims):
        index = self.index[kind]
        return jwt.encode(
            claims,
            self.keysets[kind][index],
            algorithm="ES256" if kind == "iap" else "RS256",
            headers={"kid": f"key-{index}"},
        )

    def assertion(self, **changes):
        now = int(time.time())
        claims = dict(
            iss=IAP_ISSUER,
            aud=AUD,
            sub="accounts.google.com:" + SUB,
            email=EMAIL,
            iat=now,
            exp=now + 600,
            identity_source="GOOGLE",
        )
        return self.sign("iap", {**claims, **changes})

    def issue(self, redirect, **changes):
        args = query(redirect)
        now = int(time.time())
        claims = dict(
            iss="https://accounts.google.com",
            aud=CLIENT,
            sub=SUB,
            email=EMAIL,
            email_verified=True,
            nonce=args["nonce"],
            iat=now,
            exp=now + 3600,
        )
        code = "code-" + args["state"]
        self.codes[code] = (args["code_challenge"], self.sign("oidc", {**claims, **changes}))
        return {"state": args["state"], "code": code}

    def http(self, request):
        url = str(request.url)
        self.calls.append(url)
        assert url in (IAP_KEYS, GOOGLE_KEYS, TOKEN_ENDPOINT)
        if url in self.outage:
            return httpx.Response(503)
        if url == TOKEN_ENDPOINT:
            fields = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            assert request.method == "POST" and fields["redirect_uri"] == self.callback
            assert fields["client_id"] == CLIENT and fields["client_secret"] == SETTINGS.client_secret
            assert fields["grant_type"] == "authorization_code"
            if fields["code"] not in self.codes:
                return httpx.Response(400)
            challenge, token = self.codes.pop(fields["code"])
            assert (
                base64.urlsafe_b64encode(hashlib.sha256(fields["code_verifier"].encode()).digest())
                .decode()
                .rstrip("=")
                == challenge
            )
            return httpx.Response(
                200, json={"id_token": self.oidc_token or token, "access_token": "unused-private"}
            )
        kind = "iap" if url == IAP_KEYS else "oidc"
        index = self.index[kind]
        alg = jwt.algorithms.ECAlgorithm if kind == "iap" else jwt.algorithms.RSAAlgorithm
        key = json.loads(alg.to_jwk(self.keysets[kind][index].public_key()))
        key.update(kid=f"key-{index}", use="sig")
        return httpx.Response(200, json={"keys": [key]}, headers={"Cache-Control": "max-age=15"})


@pytest.fixture
def provider(keysets):
    return Providers(keysets)


@pytest.fixture
def state(tmp_path, provider):
    return Sessions(tmp_path / "private", clock=lambda: provider.now)


@contextmanager
def client(settings, state, provider):
    app = create_app(
        settings, state, transport=httpx.MockTransport(provider.http), key_clock=lambda: provider.now
    )
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as browser:
        browser.headers.update({"x-goog-iap-jwt-assertion": provider.assertion(), "origin": ORIGIN})
        yield browser


@pytest.fixture
def browser(state, provider):
    with client(SETTINGS, state, provider) as b:
        yield b


def start(browser):
    response = browser.post("/auth/start")
    assert response.status_code == 303
    return response.headers["location"]


def callback(browser, args):
    return browser.get("/auth/callback", params=args)


def login(browser, provider, **claims):
    return callback(browser, provider.issue(start(browser), **claims))


def test_end_to_end_owner_binding_and_logout(browser, provider, state):
    assert browser.get("/owner").status_code == 403
    redirect = start(browser)
    assert redirect.split("?")[0] == AUTHORIZATION
    fields = query(redirect)
    assert (fields["scope"], fields["response_type"], fields["code_challenge_method"]) == (
        "openid email",
        "code",
        "S256",
    )
    assert fields["redirect_uri"] == SETTINGS.callback
    assert len({fields["state"], fields["nonce"], fields["code_challenge"]}) == 3
    old = browser.cookies[COOKIE]
    params = provider.issue(redirect)
    response = callback(browser, params)
    assert response.status_code == 303 and response.headers["location"] == "/"
    cookie = response.headers["set-cookie"].lower()
    assert (
        "secure" in cookie
        and "httponly" in cookie
        and "samesite=lax" in cookie
        and "domain=" not in cookie
    )
    assert old != browser.cookies[COOKIE] and not state.bound(old, PIN, SETTINGS.scope_key)
    assert browser.get("/owner").json() == {"owner_verified": True}
    assert callback(browser, params).status_code == 403 and provider.calls.count(TOKEN_ENDPOINT) == 1
    content = browser.get("/").text
    for private in (
        EMAIL,
        SUB,
        PIN,
        params["code"],
        fields["nonce"],
        "unused-private",
        SETTINGS.client_secret,
    ):
        assert private not in content
    assert browser.post("/auth/logout").status_code == 303
    assert browser.get("/owner").status_code == 403
    assert principal_key("accounts.google.com:" + SUB) == PIN


@pytest.mark.parametrize(
    "change",
    [
        {"sub": "different-id"},
        {"iss": "urn:cra2:invitation-pilot:issuer"},
        {"aud": "other-client"},
        {"azp": "other-client"},
        {"aud": [CLIENT, "another-client"]},
        {"nonce": "other"},
        {"email_verified": False},
        {"email_verified": "true"},
        {"email": "other@example.test"},
        {"exp": 1},
        {"sub": ""},
    ],
)
def test_bad_google_proof_never_establishes_owner(browser, provider, change):
    assert login(browser, provider, **change).status_code == 403
    assert browser.get("/owner").status_code == 403


@pytest.mark.parametrize(
    "change",
    [
        {"sub": "unknown-provider:" + SUB},
        {"sub": "accounts.google.com:"},
        {"sub": "accounts.google.com:other"},
        {"email": "other@example.test"},
        {"iss": "https://accounts.google.com"},
        {"aud": AUD + "-other"},
        {"identity_source": "WORKFORCE_IDENTITY"},
        {"gcip": {}},
        {"exp": 1},
        {"iat": int(time.time()) - 100, "exp": int(time.time()) + 600},
    ],
)
def test_bad_iap_proof_never_reaches_signin(browser, provider, change):
    browser.headers["x-goog-iap-jwt-assertion"] = provider.assertion(**change)
    assert browser.post("/auth/start").status_code == 403
    assert TOKEN_ENDPOINT not in provider.calls


def test_untrusted_or_unsigned_headers_and_cross_origin(browser, provider):
    assert browser.get("/healthz", headers={"x-goog-iap-jwt-assertion": "invalid"}).json() == {
        "status": "ok"
    }
    del browser.headers["x-goog-iap-jwt-assertion"]
    assert browser.get("/", headers={"x-goog-authenticated-user-email": EMAIL}).status_code == 403
    token = provider.assertion()
    assert browser.get("/", headers=[("x-goog-iap-jwt-assertion", token)] * 2).status_code == 403
    browser.headers["x-goog-iap-jwt-assertion"] = token
    assert (
        browser.post("/auth/start", headers={"origin": "https://other.example.test"}).status_code == 403
    )
    assert browser.get("/", headers={"host": "other.example.test"}).status_code == 400
    assert browser.get("/identity").status_code == 404
    assert browser.post("/action").status_code == 404
    assert browser.get("/workspace").status_code == 404


def test_fixture_credentials_and_token_substitution(browser, provider):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    fixture = jwt.encode(
        {"iss": "urn:cra2:invitation-pilot:issuer", "sub": "pilot-owner"},
        Ed25519PrivateKey.generate(),
        algorithm="EdDSA",
    )
    provider.oidc_token = fixture
    assert login(browser, provider).status_code == 403
    provider.oidc_token = provider.assertion()
    assert login(browser, provider).status_code == 403
    browser.headers["x-goog-iap-jwt-assertion"] = fixture
    assert browser.get("/").status_code == 403


def test_valid_legacy_google_issuer_and_authorized_party(browser, provider):
    assert login(browser, provider, iss="accounts.google.com", azp=CLIENT).status_code == 303


def test_verify_only_never_enrolls_and_pin_change_requires_fresh_signin(provider, state):
    initial = replace(SETTINGS, mode="verify-only", owner_pin=None)
    with client(initial, state, provider) as probe, client(SETTINGS, state, provider) as enrolled:
        assert login(probe, provider).status_code == 303
        assert "private enrollment" in probe.get("/").text and probe.get("/owner").status_code == 403
        enrolled.cookies.update(probe.cookies)
        assert enrolled.get("/owner").status_code == 403
        assert login(enrolled, provider).status_code == 303
        assert enrolled.get("/owner").status_code == 200
        wrong = replace(SETTINGS, owner_pin=principal_key("accounts.google.com:different"))
        with client(wrong, state, provider) as changed:
            changed.cookies.update(enrolled.cookies)
            assert changed.get("/owner").status_code == 403
            assert changed.post("/auth/start").status_code == 403


def test_account_switch_at_callback_in_probe_consumes_attempt(provider, state):
    initial = replace(SETTINGS, mode="verify-only", owner_pin=None)
    with client(initial, state, provider) as b:
        params = provider.issue(start(b))
        b.headers["x-goog-iap-jwt-assertion"] = provider.assertion(sub="accounts.google.com:other")
        assert callback(b, params).status_code == 403
        b.headers["x-goog-iap-jwt-assertion"] = provider.assertion()
        assert callback(b, params).status_code == 403
        assert TOKEN_ENDPOINT not in provider.calls


def test_every_protected_request_rechecks_iap(browser, provider):
    assert login(browser, provider).status_code == 303
    browser.headers["x-goog-iap-jwt-assertion"] = provider.assertion(sub="accounts.google.com:other")
    assert browser.get("/owner").status_code == 403
    del browser.headers["x-goog-iap-jwt-assertion"]
    assert browser.get("/owner").status_code == 403


def test_one_attempt_across_clients_and_restart(browser, provider, state):
    params = provider.issue(start(browser))
    reopened = Sessions(Path(state.path).parent, clock=lambda: provider.now)
    with client(SETTINGS, reopened, provider) as second:
        assert callback(second, params).status_code == 403
        second.cookies.update(browser.cookies)
        with ThreadPoolExecutor(2) as workers:
            replies = list(workers.map(lambda b: callback(b, params).status_code, [browser, second]))
        assert sorted(replies) == [303, 403]
    assert provider.calls.count(TOKEN_ENDPOINT) == 1


def test_redirect_parameters_and_expiry(browser, provider):
    params = provider.issue(start(browser))
    assert callback(browser, {**params, "state": "other"}).status_code == 403
    assert (
        browser.get("/auth/callback", params=[*params.items(), ("state", params["state"])]).status_code
        == 403
    )
    assert callback(browser, {**params, "iss": "unrecognized"}).status_code == 403
    assert callback(browser, params).status_code == 403
    params = provider.issue(start(browser))
    provider.now += 300
    assert callback(browser, params).status_code == 403
    assert TOKEN_ENDPOINT not in provider.calls
    assert login(browser, provider).status_code == 303
    provider.now += 900
    assert browser.get("/owner").status_code == 403


def test_cancelled_or_expired_exchange_cannot_issue_session(state, provider):
    sid, attempt = state.start("", PIN, SETTINGS.scope_key)
    state.consume(sid, attempt.state, PIN, SETTINGS.scope_key)
    state.forget(sid)
    with pytest.raises(Denied):
        state.establish(sid, PIN, SETTINGS.scope_key)
    sid, attempt = state.start("", PIN, SETTINGS.scope_key)
    state.consume(sid, attempt.state, PIN, SETTINGS.scope_key)
    provider.now += 300
    with pytest.raises(Denied):
        state.establish(sid, PIN, SETTINGS.scope_key)


@pytest.mark.parametrize("kind,endpoint", [("iap", IAP_KEYS), ("oidc", GOOGLE_KEYS)])
def test_key_rotation_outage_and_recovery(browser, provider, kind, endpoint):
    assert login(browser, provider).status_code == 303
    provider.now += 16
    provider.outage.add(endpoint)
    assert (browser.get("/owner") if kind == "iap" else login(browser, provider)).status_code == 503
    provider.outage.clear()
    provider.now += 11
    provider.index[kind] = 1
    browser.headers["x-goog-iap-jwt-assertion"] = provider.assertion()
    assert login(browser, provider).status_code == 303
    assert browser.get("/owner").status_code == 200


def test_failed_exchange_replay_and_no_leak(browser, provider):
    params = provider.issue(start(browser))
    provider.outage.add(TOKEN_ENDPOINT)
    response = callback(browser, params)
    assert response.status_code == 503 and params["code"] not in response.text
    provider.outage.clear()
    assert callback(browser, params).status_code == 403
    assert browser.get("/owner").status_code == 403


@pytest.mark.parametrize(
    "change",
    [
        {"origin": "http://stage.example.test"},
        {"origin": "https://stage.example.test/path"},
        {"owner_pin": None},
        {"owner_pin": "test-subject"},
        {"mode": "verify-only"},
        {"client_secret": ""},
        {"audience": "/projects/123/locations/us-west1/services/cra2-owner-demo"},
        {"owner_email": "owner"},
    ],
)
def test_invalid_configuration_fails_closed(change):
    with pytest.raises(ValueError):
        replace(SETTINGS, **change)


def test_missing_configuration_never_uses_fixture(monkeypatch):
    monkeypatch.delenv("INVITATION_STAGE_CLIENT_ID", raising=False)
    with pytest.raises(KeyError):
        from_env()


@pytest.mark.parametrize("kind", ["iap", "oidc"])
def test_untrusted_signature_with_expected_key_id(browser, provider, kind):
    # Sign with an independent key of the correct algorithm and claim the current key ID.
    if kind == "iap":
        good = provider.assertion()
        alg = "ES256"
    else:
        params = provider.issue(start(browser))
        good = provider.codes[params["code"]][1]
        alg = "RS256"
    claims = jwt.decode(good, options={"verify_signature": False})
    bad = jwt.encode(claims, provider.keysets[kind][1], algorithm=alg, headers={"kid": "key-0"})
    if kind == "iap":
        browser.headers["x-goog-iap-jwt-assertion"] = bad
        assert browser.get("/").status_code == 403
    else:
        provider.oidc_token = bad
        assert callback(browser, params).status_code == 403
    assert browser.get("/owner").status_code == 403


@pytest.mark.skipif(
    os.environ.get("INVITATION_BROWSER") != "1", reason="opt-in installed Chrome/Playwright probe"
)
def test_staging_cross_site_https_browser(tmp_path, state, provider):
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-nodes",
            "-newkey",
            "rsa:2048",
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-keyout",
            str(key),
            "-out",
            str(cert),
        ],
        capture_output=True,
        check=True,
    )
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        origin = f"https://127.0.0.1:{port}"
        settings = replace(SETTINGS, origin=origin)
        provider.callback = settings.callback
        stage = create_app(settings, state, transport=httpx.MockTransport(provider.http))

        # Chrome resolves the Google hostname to this loopback TLS listener.
        # The fake edge signs IAP requests only for the staging origin.
        async def fixture(scope, receive, send):
            if scope["type"] == "http":
                host = dict(scope["headers"]).get(b"host")
                if host == b"accounts.google.com":
                    assert scope["path"] == urlsplit(AUTHORIZATION).path
                    params = provider.issue(AUTHORIZATION + "?" + scope["query_string"].decode())
                    callback_url = settings.callback + "?" + urlencode(params)
                    await HTMLResponse(
                        f'<a href="{escape(callback_url, quote=True)}">Continue as test owner</a>'
                    )(scope, receive, send)
                    return
                if host == urlsplit(origin).netloc.encode():
                    scope = {
                        **scope,
                        "headers": [
                            *scope["headers"],
                            (b"x-goog-iap-jwt-assertion", provider.assertion().encode()),
                        ],
                    }
            await stage(scope, receive, send)

        server = uvicorn.Server(
            uvicorn.Config(
                fixture,
                ssl_certfile=str(cert),
                ssl_keyfile=str(key),
                access_log=False,
                log_level="error",
                proxy_headers=False,
            )
        )
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    pytest.fail("Loopback HTTPS fixture did not start")
                time.sleep(0.05)
            result = subprocess.run(
                ["node", str(Path(__file__).with_name("staging_browser.cjs")), origin],
                capture_output=True,
                text=True,
                timeout=45,
            )
            assert result.returncode == 0, result.stderr
            assert provider.calls.count(TOKEN_ENDPOINT) == 1
        finally:
            server.should_exit = True
            thread.join(8)


def test_staging_factory_is_independent_and_serves_identity_only(tmp_path, monkeypatch):
    values = {
        "ORIGIN": ORIGIN,
        "IAP_AUDIENCE": AUD,
        "CLIENT_ID": CLIENT,
        "CLIENT_SECRET": SETTINGS.client_secret,
        "OWNER_EMAIL": EMAIL,
        "MODE": "verify-only",
        "STATE_DIR": str(tmp_path / "private"),
    }
    for k, v in values.items():
        monkeypatch.setenv("INVITATION_STAGE_" + k, v)
    monkeypatch.delenv("INVITATION_STAGE_OWNER_PIN", raising=False)
    app = from_env()
    with TestClient(app, base_url=ORIGIN) as b:
        assert b.get("/healthz").json() == {"status": "ok"}
        assert b.get("/").status_code == 403
        assert b.post("/action", headers={"Origin": ORIGIN}).status_code == 404
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from invitations.staging.app import from_env; from_env(); "
            "assert not {'week2','cra2','invitations.identity','invitations.fixtures','invitations.worker'} & sys.modules.keys()",
        ],
        check=True,
    )


def test_cross_client_code_or_missing_state_cannot_create_session(browser, provider):
    params = provider.issue(start(browser))
    assert callback(browser, {"code": params["code"]}).status_code == 403
    assert callback(browser, {**params, "code": "unknown-code"}).status_code == 403
    assert callback(browser, params).status_code == 403
    assert browser.get("/owner").status_code == 403


def test_manual_enrollment_reads_only_a_unique_completed_probe(provider, state):
    config = replace(SETTINGS, mode="verify-only", owner_pin=None)
    provider.now = time.time()
    directory = state.path.parent
    with client(config, state, provider) as b:
        params = provider.issue(start(b))
        with pytest.raises(ValueError):
            enrollment_candidate(config, directory)
        assert callback(b, params).status_code == 303
        assert enrollment_candidate(config, directory) == PIN
        assert b.get("/owner").status_code == 403
        with pytest.raises(ValueError):
            enrollment_candidate(SETTINGS, directory)
        with pytest.raises(ValueError):
            enrollment_candidate(
                replace(config, client_id="other.apps.googleusercontent.com"), directory
            )
        with client(config, state, provider) as other:
            other.headers["x-goog-iap-jwt-assertion"] = provider.assertion(
                sub="accounts.google.com:second-id"
            )
            assert login(other, provider, sub="second-id").status_code == 303
            with pytest.raises(ValueError):
                enrollment_candidate(config, directory)


def test_candidate_command_refuses_unverified_state(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["invitations.staging", "candidate-pin"])
    monkeypatch.delenv("INVITATION_STAGE_MODE", raising=False)
    with pytest.raises(SystemExit) as exc:
        candidate_command()
    assert exc.value.code == 1
    assert capsys.readouterr().out == ""
