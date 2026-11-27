"""Run with the final image's Python via stdin, inside an offline smoke container."""

from dataclasses import replace
from importlib.util import find_spec
import json
import os
import sys
from tempfile import TemporaryDirectory
import time
from urllib.parse import parse_qs, urlsplit

from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi.testclient import TestClient
import httpx
import jwt

from invitations.staging.app import create_app, from_env
from invitations.staging.google import (
    GOOGLE_KEYS, IAP_ISSUER, IAP_KEYS, TOKEN_ENDPOINT, Settings, principal_key,
)
from invitations.staging.sessions import Sessions


def verify_entrypoint(settings):
    routes = {(method, route.path) for route in from_env().routes for method in route.methods}
    assert routes == {
        ("GET", "/"), ("GET", "/healthz"), ("GET", "/auth/callback"),
        ("GET", "/owner"), ("POST", "/auth/start"), ("POST", "/auth/logout"),
    }
    with httpx.Client(
        base_url=f"http://127.0.0.1:{os.environ['PORT']}",
        headers={"Host": urlsplit(settings.origin).netloc, "Origin": settings.origin},
        trust_env=False,
        timeout=1,
    ) as client:
        deadline = time.monotonic() + 10
        while True:
            try:
                assert client.get("/healthz").json() == {"status": "ok"}
                break
            except httpx.ConnectError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.1)
        assert client.get("/").status_code == 403
        assert client.get("/owner").status_code == 403
        assert client.get("/auth/callback?code=synthetic-callback-log-marker").status_code == 403
        for path in ("/identity", "/callback", "/workspace", "/report", "/docs", "/openapi.json"):
            assert client.get(path).status_code == 404, path
        assert client.post("/action").status_code == 404
    print("Entrypoint honors PORT, exposes exactly six routes, and denies unsigned identity.")


def verify_signed_owner(settings):
    iap_key = ec.generate_private_key(ec.SECP256R1())
    google_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    iap_jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(iap_key.public_key()))
    google_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(google_key.public_key()))
    sub = "1234567890"
    namespaced_sub = "accounts.google.com:" + sub
    settings = replace(settings, mode="enrolled", owner_pin=principal_key(namespaced_sub))
    now = int(time.time())
    assertion = jwt.encode(
        dict(iss=IAP_ISSUER, aud=settings.audience, sub=namespaced_sub,
             email=settings.owner_email, iat=now, exp=now + 300),
        iap_key, algorithm="ES256", headers={"kid": "iap"},
    )
    id_token = None
    exchanges = 0

    def provider(request):
        nonlocal exchanges
        url = str(request.url)
        if url == IAP_KEYS:
            return httpx.Response(200, json={"keys": [dict(iap_jwk, kid="iap")]})
        if url == GOOGLE_KEYS:
            return httpx.Response(200, json={"keys": [dict(google_jwk, kid="google")]})
        assert url == TOKEN_ENDPOINT and request.method == "POST"
        fields = parse_qs(request.content.decode())
        assert fields["client_secret"] == [settings.client_secret]
        assert fields["redirect_uri"] == [settings.callback]
        exchanges += 1
        return httpx.Response(200, json={"id_token": id_token})

    with TemporaryDirectory() as state_dir:
        app = create_app(settings, Sessions(state_dir), transport=httpx.MockTransport(provider))
        with TestClient(
            app, base_url=settings.origin, follow_redirects=False,
            headers={"x-goog-iap-jwt-assertion": assertion, "Origin": settings.origin},
        ) as client:
            assert client.get("/owner").status_code == 403
            for subject, expected in (("0987654321", 403), (sub, 303)):
                start = client.post("/auth/start")
                assert start.status_code == 303
                challenge = parse_qs(urlsplit(start.headers["location"]).query)
                id_token = jwt.encode(
                    dict(iss="https://accounts.google.com", aud=settings.client_id, sub=subject,
                         email=settings.owner_email, email_verified=True, nonce=challenge["nonce"][0],
                         iat=now, exp=now + 300),
                    google_key, algorithm="RS256", headers={"kid": "google"},
                )
                params = {"state": challenge["state"][0], "code": "test-only"}
                assert client.get("/auth/callback", params=params).status_code == expected
                assert client.get("/auth/callback", params=params).status_code == 403
                assert client.get("/owner").status_code == (200 if expected == 303 else 403)
            assert exchanges == 2
            assert client.post("/auth/logout").status_code == 303
            assert client.get("/owner").status_code == 403
    print("Synthetic signed owner bound. Subject mismatch, callback replay and post-logout access denied.")


if __name__ == "__main__":
    assert sys.version_info[:2] == (3, 13) and os.getuid() == os.getgid() == 65532
    excluded = ("__main__", "fixtures", "identity", "web", "worker", "service", "staging.__main__", "tests")
    assert not any(find_spec(f"invitations.{name}") for name in excluded)
    print(f"Python {sys.version.split()[0]}, UID/GID 65532. Eight excluded modules absent.")
    settings = Settings.from_env()
    verify_entrypoint(settings)
    verify_signed_owner(settings)
