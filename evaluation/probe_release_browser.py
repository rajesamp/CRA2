"""Read the C5 release label in signed local Chrome and inspect the anonymous intro."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time
from unittest.mock import patch

import httpx
import uvicorn

from week2 import release_info
from week2.cloud_app import create_app
from week2.iap import IAPSettings, IAPKeys, IAPVerifier
from week2.landing import create_app as landing
from week2.tests.test_iap import AUDIENCE, OWNER, identity, token
from week2.tests.test_cloud_storage import ObjectFixture


@contextmanager
def running(app):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        origin = f"http://127.0.0.1:{sock.getsockname()[1]}"
        server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False, proxy_headers=False))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 30
            while not server.started:
                if not thread.is_alive() or time.monotonic() >= deadline:
                    raise RuntimeError("signed fixture did not start")
                time.sleep(.05)
            yield origin
        finally:
            server.should_exit = True
            thread.join(15)


def browser(origin, operation, **inputs):
    result = subprocess.run(["node", str(Path(__file__).with_name("answer_browser.cjs"))],
                            input=json.dumps({"origin": origin, "operation": operation, **inputs}),
                            text=True, capture_output=True, timeout=60)
    if result.returncode:
        raise RuntimeError(f"Chrome could not verify the {operation} page")
    return json.loads(result.stdout)


def verify(temp, label):
    keypair = identity.__wrapped__()
    canaries = [OWNER, "private-release-field-canary", label["bundle"]]
    result = {}
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"keys":[keypair[1]]}))) as jwks:
        settings = IAPSettings(AUDIENCE, OWNER)
        verifier = IAPVerifier(settings, keys=IAPKeys(client=jwks))
        stores = ObjectFixture(temp / "objects.sqlite3").stores()
        for state, value in (("packaged", label), ("missing", None), ("invalid", {**label,"private":canaries[1]})):
            path = temp / (state + ".json")
            if value is not None:
                path.write_text(json.dumps(value))
            with patch.object(release_info, "LABEL_FILE", path):
                protected = create_app(settings=settings, verifier=verifier, stores=stores)
                with running(protected) as origin:
                    assert httpx.get(origin + "/config").status_code == 401
                    observed = browser(origin, "release", assertion=token(keypair))["text"]
                expected = release_info.render_label(label) if state == "packaged" else release_info.FALLBACK
                if observed != expected:
                    raise ValueError(f"{state} release label mismatch")
                result[state] = observed
    with running(landing("https://protected-synthetic.a.run.app/")) as origin:
        public = browser(origin, "intro", canaries=canaries)
        assert public == {"private_content":False, "protected_label":0}
        redirect = httpx.get(origin + "/signin", follow_redirects=False)
        assert redirect.status_code == 303 and redirect.headers["location"] == "https://protected-synthetic.a.run.app/"
        assert not any(canary in str(redirect.headers) + redirect.text for canary in canaries)
    return {"owner_labels": result, "anonymous_intro": public, "fixed_redirect": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    record = json.loads(args.identity.read_bytes())
    with tempfile.TemporaryDirectory() as tmp:
        output = verify(Path(tmp), release_info.label_fields(record["source"], record["dataset"]))
    args.out.write_text(json.dumps(output, indent=2) + "\n")
