"""Anonymous introduction cannot expose identity, private APIs or an open redirect."""
import pytest
from fastapi.testclient import TestClient

from week2.landing import create_app

TARGET = "https://protected-synthetic.a.run.app/"


def test_public_intro_and_fixed_signin_have_no_private_content():
    client = TestClient(create_app(TARGET))
    page = client.get("/")
    assert page.status_code == 200 and "Sign in with Google" in page.text
    assert "Understand the change" in page.text and "V2 · PLANNED" in page.text
    assert TARGET not in page.text and "@" not in page.text and "Logged in users" not in page.text
    assert "set-cookie" not in page.headers and "default-src 'none'" in page.headers["content-security-policy"]
    assert client.get("/styles.css").headers["content-type"].startswith("text/css")
    redirect = client.get("/signin?next=https://attacker.example.test", follow_redirects=False)
    assert redirect.status_code == 303 and redirect.headers["location"] == TARGET
    assert redirect.headers["cache-control"] == "no-store"
    assert client.head("/").status_code == 200


@pytest.mark.parametrize("path", ["/config", "/users", "/docs", "/openapi.json", "/gradio_api/queue/join",
    "/gradio_api/queue/data", "/gradio_api/file=/app/data/team_settings.json", "/upload", "/../week2/cloud_app.py"])
def test_public_entrypoint_cannot_route_to_private_features(path):
    client = TestClient(create_app(TARGET))
    for method in (client.get, client.post):
        assert method(path).status_code == 404


@pytest.mark.parametrize("target", ["", "http://protected-synthetic.a.run.app", "https://evil.example.test",
    "https://protected-synthetic.a.run.app.evil.test", "https://user:secret@protected-synthetic.a.run.app",
    "https://protected-synthetic.a.run.app:443", "https://protected-synthetic.a.run.app/?next=evil", "https://protected-synthetic.a.run.app/#evil"])
def test_signin_target_configuration_fails_closed(target):
    with pytest.raises(ValueError):
        create_app(target)
