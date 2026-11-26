import re
import time

from fastapi.testclient import TestClient
import jwt
import pytest

from invitations.identity import AUDIENCE, ISSUER, Login, RECIPIENT
from invitations.web import create_app


def test_browser_security(pilot):
    api = create_app(pilot.store.directory, pilot=pilot)
    origin = "https://127.0.0.1"
    with TestClient(api, base_url=origin) as client:
        response = client.get("/")
        csrf = re.search('name="csrf" value="([^"]+)"', response.text)[1]
        cookie = response.headers["set-cookie"].lower()
        assert "secure" in cookie and "httponly" in cookie and "samesite=strict" in cookie
        form = {"csrf": csrf, "op": "start", "email": RECIPIENT.email}
        assert client.post("/action", data=form).status_code == 403
        assert (
            client.post("/action", data={**form, "csrf": "bad"}, headers={"origin": origin}).status_code
            == 403
        )
        assert (
            client.post("/action", data={**form, "op": "pause"}, headers={"origin": origin}).status_code
            == 403
        )
        assert client.get("/workspace").status_code == 403
        assert client.get("/report").status_code == 403
        assert client.get("/", headers={"host": "untrusted.test"}).status_code == 400
        assert client.post("/action", json=form, headers={"origin": origin}).status_code == 415

        def post(values):
            return client.post(
                "/action",
                data={"csrf": csrf, **values},
                headers={"origin": origin},
                follow_redirects=False,
            )

        assert post(form).status_code == 303
        assert post({"op": "authenticate", "key": "bad"}).status_code == 400
        auth = post({"op": "authenticate", "key": Login(pilot.store).key(RECIPIENT)})
        assert auth.status_code == 303
        url = auth.headers["location"]
        assert client.get(url + "wrong").status_code == 403
        assert client.get(url, follow_redirects=False).status_code == 303
        assert client.get(url).status_code == 403
        csrf = re.search('name="csrf" value="([^"]+)"', client.get("/").text)[1]
        assert post({"op": "resume", "owner": "true"}).status_code == 403
        assert client.get("/report").status_code == 403


@pytest.mark.parametrize(
    "updated",
    [
        {"iss": "untrusted"},
        {"aud": "other"},
        {"email_verified": False},
        {"exp": 1},
        {"nonce": "wrong"},
        {"sub": "something-else"},
        {"email": "owner@example.test"},
    ],
)
def test_fixture_identity_claims(pilot, updated):
    login = Login(pilot.store)
    issued = int(time.time())
    claims = dict(
        iss=ISSUER,
        aud=AUDIENCE,
        sub=RECIPIENT.subject,
        email=RECIPIENT.email,
        email_verified=True,
        nonce="expected",
        iat=issued,
        exp=issued + 60,
    )
    assertion = jwt.encode({**claims, **updated}, login.signer, algorithm="EdDSA")
    with pytest.raises((ValueError, jwt.InvalidTokenError)):
        login.verify(assertion, "expected")
