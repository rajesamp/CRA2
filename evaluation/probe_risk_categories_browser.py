"""Verify category evidence and stale-result suppression in signed local Chrome."""
import json
from pathlib import Path
import subprocess
import tempfile

import httpx

from evaluation.probe_release_browser import browser, running
from week2.cloud_app import create_app
from week2.iap import IAPKeys, IAPSettings, IAPVerifier
from week2.landing import create_app as landing
from week2.tests.test_cloud_storage import ObjectFixture
from week2.tests.test_iap import AUDIENCE, OWNER, identity, token


def verify(temp):
    keys = identity.__wrapped__()
    settings = IAPSettings(AUDIENCE, OWNER)
    markers = ["orchid-fixture", "cedar-fixture", "willow-fixture"]
    observed = {}
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"keys": [keys[1]]}))) as jwks:
        verifier = IAPVerifier(settings, keys=IAPKeys(client=jwks))
        for mode in ("protected", "capacity"):
            local = mode == "capacity"
            api = create_app(settings=settings, verifier=verifier,
                             stores=ObjectFixture(temp / (mode + ".sqlite3")).stores(),
                             local_capacity_path=temp / "limits.sqlite3" if local else None)
            with running(api) as origin:
                assert httpx.get(origin + "/config").status_code == 401
                assert httpx.get(origin + "/config", headers={"x-goog-iap-jwt-assertion":
                                 token(keys, email="unlisted@example.test")}).status_code == 403
                config = {"origin": origin, "assertion": token(keys), "markers": markers, "capacity": local}
                result = subprocess.run(["node", str(Path(__file__).with_name("risk_categories_browser.cjs"))],
                                        input=json.dumps(config), capture_output=True, text=True, timeout=165)
                if result.returncode:
                    raise RuntimeError(f"{mode} browser failed: {result.stderr[-1800:]}")
                observed[mode] = json.loads(result.stdout)
    with running(landing("https://protected-synthetic.a.run.app/")) as origin:
        private = [*markers, "Risk by category"]
        assert browser(origin, "intro", canaries=private) == {"private_content": False, "protected_label": 0}
        redirect = httpx.get(origin + "/signin", follow_redirects=False)
        assert redirect.status_code == 303 and redirect.headers["location"] == "https://protected-synthetic.a.run.app/"
        assert all(m not in str(redirect.headers) + redirect.text for m in private)
    return {**observed, "anonymous_intro_and_redirect": "passed"}


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(dir="/tmp") as directory:
        print(json.dumps(verify(Path(directory)), sort_keys=True))
