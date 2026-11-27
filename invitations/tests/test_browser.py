"""Drive the actual standalone process in Chrome with independent browser profiles."""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

import pytest

from invitations.identity import Login, OWNER, RECIPIENT, SECOND
from invitations.service import Pilot


@pytest.mark.skipif(
    os.environ.get("INVITATION_BROWSER") != "1", reason="opt-in installed Chrome/Playwright probe"
)
def test_signed_browser(tmp_path):
    state = tmp_path / "browser"
    pilot = Pilot(state, OWNER)
    login = Login(pilot.store)
    earlier = Pilot(state, OWNER, clock=lambda: time.time() - 601)
    earlier.hold(OWNER, False)
    expired_id = earlier.send(OWNER, SECOND.email)
    earlier.dispatch(expired_id)
    expired_code = earlier.local.read_code(expired_id)
    earlier.hold(OWNER, True)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    server = subprocess.Popen(
        [sys.executable, "-m", "invitations", "--state", str(state), "serve", "--port", str(port)]
    )
    try:
        limit = time.monotonic() + 15
        while time.monotonic() < limit:
            try:
                with urlopen(origin, timeout=1) as resp:
                    if resp.status == 200:
                        break
            except OSError:
                if server.poll() is not None:
                    pytest.fail("Invitation server exited")
                time.sleep(0.05)
        config = {
            "origin": origin,
            "expiredCode": expired_code,
            "python": sys.executable,
            "state": str(state),
            "accounts": [[p.email, login.key(p)] for p in (OWNER, RECIPIENT, SECOND)],
        }
        result = subprocess.run(
            ["node", str(Path(__file__).with_name("browser.cjs"))],
            input=json.dumps(config),
            capture_output=True,
            text=True,
            timeout=90,
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == {
            "reviewed": 1,
            "redeemed": 1,
            "revoked": 1,
            "denied": 1,
            "direct": 1,
        }
    finally:
        server.terminate()
        server.wait(timeout=10)
