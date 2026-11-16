"""Real ES256 signatures and fail-closed IAP boundary checks; no Google calls."""
import json
import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from week2.iap import IAPKeys, IAPMiddleware, IAPSettings, IAPVerifier

AUDIENCE = "/projects/123456789/locations/test-region/services/test-service"
OWNER = "owner@example.test"


@pytest.fixture
def identity():
    private = ec.generate_private_key(ec.SECP256R1())
    jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(private.public_key()))
    jwk.update(kid="key-one", alg="ES256", use="sig")
    now = int(time.time())
    claims = dict(iss="https://cloud.google.com/iap", aud=AUDIENCE, sub="test-subject",
                  email=OWNER, iat=now, exp=now + 600)
    return private, jwk, claims


def token(identity, **changes):
    private, _, claims = identity
    return jwt.encode(dict(claims, **changes), private, algorithm="ES256", headers={"kid": "key-one"})


def protected(identity, *, transport=None, clock=time.monotonic):
    _, jwk, _ = identity
    client = httpx.Client(transport=transport or httpx.MockTransport(
        lambda req: httpx.Response(200, json={"keys": [jwk]}, headers={"cache-control": "max-age=60"})))
    keys = IAPKeys(client=client, clock=clock)
    verifier = IAPVerifier(IAPSettings(AUDIENCE, OWNER), keys=keys)
    app = FastAPI()

    @app.api_route("/{path:path}", methods=["GET", "POST"])
    def entered(request: Request, path: str):
        return {"identity": request.state.cra2_principal.key}

    return TestClient(IAPMiddleware(app, verifier)), keys


def test_owner_has_stable_pseudonymous_subject(identity):
    client, _ = protected(identity)
    response = client.get("/config", headers={"x-goog-iap-jwt-assertion": token(identity)})
    assert response.status_code == 200
    key = response.json()["identity"]
    assert key.startswith("iap:") and len(key) == 68
    assert OWNER not in response.text and "test-subject" not in response.text
    another, _ = protected(identity)
    assert another.get("/", headers={"x-goog-iap-jwt-assertion": token(identity)}).json()["identity"] == key


@pytest.mark.parametrize("path", ["/", "/config", "/gradio_api/queue/join",
    "/gradio_api/queue/data?session_hash=stolen", "/gradio_api/file=/app/data/team_settings.json", "/docs"])
def test_all_application_paths_reject_unsigned_identity(identity, path):
    client, _ = protected(identity)
    response = client.get(path, headers={"x-goog-authenticated-user-email": OWNER,
        "x-goog-authenticated-user-id": "test-subject", "x-forwarded-for": "127.0.0.1"})
    assert response.status_code == 401
    assert "identity" not in response.text and OWNER not in response.text


@pytest.mark.parametrize("changes", [
    {"aud": "wrong-service"}, {"aud": [AUDIENCE]}, {"iss": "https://attacker.test"},
    {"exp": 1}, {"iat": 4102444800}, {"sub": ""}, {"email": ""},
    {"exp": 4102444800}, {"iat": True},
])
def test_invalid_signed_claims_fail_closed(identity, changes):
    client, _ = protected(identity)
    assert client.get("/", headers={"x-goog-iap-jwt-assertion": token(identity, **changes)}).status_code == 401


def test_other_verified_google_identity_is_not_invited(identity):
    client, _ = protected(identity)
    response = client.get("/", headers={"x-goog-iap-jwt-assertion": token(identity, email="other@example.test")})
    assert response.status_code == 403


def test_wrong_signature_and_algorithm_are_rejected(identity):
    client, _ = protected(identity)
    other = ec.generate_private_key(ec.SECP256R1())
    forged = jwt.encode(identity[2], other, algorithm="ES256", headers={"kid": "key-one"})
    wrong_alg = jwt.encode(identity[2], "synthetic-hmac-test-key-that-is-long-enough", algorithm="HS256", headers={"kid": "key-one"})
    for value in (forged, wrong_alg, "malformed", "x" * 9000):
        assert client.get("/", headers={"x-goog-iap-jwt-assertion": value}).status_code == 401


def test_missing_claim_and_duplicate_assertion_rejected(identity):
    client, _ = protected(identity)
    claims = dict(identity[2]); del claims["exp"]
    missing = jwt.encode(claims, identity[0], algorithm="ES256", headers={"kid": "key-one"})
    assert client.get("/", headers={"x-goog-iap-jwt-assertion": missing}).status_code == 401
    signed = token(identity)
    assert client.get("/", headers=[("x-goog-iap-jwt-assertion", signed)] * 2).status_code == 401


def test_health_is_content_free_and_exact_get_only(identity):
    client, _ = protected(identity)
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.post("/healthz").status_code == 401
    assert client.get("/healthz/").status_code == 401


def test_websocket_is_rejected_before_handler(identity):
    client, _ = protected(identity)
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect('/socket'):
            pytest.fail('Unauthenticated websocket was accepted')
    assert error.value.code == 1008


def test_fetch_failure_never_admits_and_does_not_expose_error(identity):
    def failed(request):
        raise httpx.ConnectError("private-network-canary", request=request)
    client, _ = protected(identity, transport=httpx.MockTransport(failed))
    response = client.get("/", headers={"x-goog-iap-jwt-assertion": token(identity)})
    assert response.status_code == 503
    assert "canary" not in response.text


def test_expired_keys_cannot_be_used_after_refresh_failure(identity):
    now = [100.]; calls = []
    def fetch(request):
        calls.append(request)
        if len(calls) > 1:return httpx.Response(503)
        return httpx.Response(200, json={"keys": [identity[1]]}, headers={"cache-control": "max-age=10"})
    client, _ = protected(identity, transport=httpx.MockTransport(fetch), clock=lambda: now[0])
    headers = {"x-goog-iap-jwt-assertion": token(identity)}
    assert client.get("/", headers=headers).status_code == 200
    now[0] += 11
    assert client.get("/", headers=headers).status_code == 503
    assert client.get("/", headers=headers).status_code == 503
    assert len(calls) == 2  # Failure backoff also bounds outbound requests.


def test_key_rotation_and_fixed_endpoint(identity):
    now = [100.]; served = [identity[1]]; calls = []
    def fetch(request):
        calls.append(str(request.url))
        return httpx.Response(200, json={"keys": list(served)}, headers={"cache-control": "max-age=60"})
    client, _ = protected(identity, transport=httpx.MockTransport(fetch), clock=lambda: now[0])
    assert client.get("/", headers={"x-goog-iap-jwt-assertion": token(identity)}).status_code == 200
    private = ec.generate_private_key(ec.SECP256R1())
    second = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(private.public_key()))
    second.update(kid="key-two", alg="ES256", use="sig"); served.append(second)
    now[0] += 11
    rotated = jwt.encode(identity[2], private, algorithm="ES256", headers={"kid": "key-two"})
    assert client.get("/", headers={"x-goog-iap-jwt-assertion": rotated}).status_code == 200
    assert calls == ["https://www.gstatic.com/iap/verify/public_key-jwk"] * 2


@pytest.mark.parametrize("document", [{"keys": []}, {"keys": "not-a-list"}, {"keys": [{"kid": "bad"}]}, {"keys": [{"kty": "oct", "kid": "key-one", "k": "secret"}]}])
def test_malformed_key_documents_fail_closed(identity, document):
    client, _ = protected(identity, transport=httpx.MockTransport(lambda req: httpx.Response(200, json=document)))
    assert client.get("/", headers={"x-goog-iap-jwt-assertion": token(identity)}).status_code == 503


@pytest.mark.parametrize("audience,owner", [("", OWNER), ("wildcard", OWNER), (AUDIENCE, ""), (AUDIENCE, "*"), (AUDIENCE, OWNER + ",other@example.test")])
def test_configuration_requires_exact_audience_and_single_owner(audience, owner):
    with pytest.raises(ValueError):IAPSettings(audience, owner)
