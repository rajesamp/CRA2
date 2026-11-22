"""Run the capacity rehearsal against a temporary loopback app and synthetic IAP identities."""
import argparse
from collections import Counter
import json
from pathlib import Path
import platform
import secrets
import socket
import subprocess
import tempfile
import threading
import time

import gradio
import httpx
from starlette.datastructures import MutableHeaders
from starlette.responses import Response
import uvicorn

from week2.capacity import LocalCapacity
from week2.cloud_app import create_app
from week2.iap import IAPKeys, IAPSettings, IAPVerifier
from week2.tests.test_cloud_storage import ObjectFixture
from week2.tests.test_iap import AUDIENCE, OWNER, identity, token


def percentiles(samples):
    ordered = sorted(samples)
    if not ordered:
        return {"n": 0, "p50_ms": None, "p95_ms": None}
    from math import ceil
    return {"n": len(ordered), **{f"p{p}_ms": round(ordered[ceil(len(ordered) * p / 100) - 1], 2)
                                  for p in (50, 95)}}


def run(root, scenario):
    keypair = identity.__wrapped__()
    member = "second@example.test"
    settings = IAPSettings(AUDIENCE, OWNER, (member,))
    keys = IAPKeys(client=httpx.Client(transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json={"keys": [keypair[1]]}))))
    db_path = root / "private" / "capacity.db"
    protected = create_app(settings=settings, verifier=IAPVerifier(settings, keys=keys),
                           stores=ObjectFixture(root / "fixture.db").stores(), local_capacity_path=db_path)
    ledger = LocalCapacity(db_path)
    identities = {secrets.token_hex(32): (email, f"local-reviewer-{i}") for i, email in enumerate((OWNER, member))}
    streams = protected.app.streams
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        host = f"127.0.0.1:{sock.getsockname()[1]}"

        async def fixture(scope, receive, send):
            if scope["type"] == "http":
                headers = MutableHeaders(scope=scope)
                person = identities.get(headers.get("x-local-test-identity", ""))
                if headers.get("host") != host or person is None:
                    return await Response(status_code=403)(scope, receive, send)
                del headers["x-local-test-identity"]
                now = int(time.time())
                headers["x-goog-iap-jwt-assertion"] = token(keypair, email=person[0], sub=person[1], iat=now, exp=now+90)
            await protected(scope, receive, send)

        server = uvicorn.Server(uvicorn.Config(fixture, log_level="error", access_log=False))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        deadline = time.monotonic() + 20
        while not server.started:
            if not thread.is_alive() or time.monotonic() >= deadline:
                raise RuntimeError("Local browser fixture failed to start")
            time.sleep(0.05)
        driver = Path(__file__).with_name("capacity_browser.cjs")
        rows = {}
        maxima = {"running": 0, "waiting": 0}
        try:
            with subprocess.Popen(["node", str(driver)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True) as child:
                child.stdin.write(json.dumps({"origin": f"http://{host}", "identities": list(identities), "scenario": scenario}))
                child.stdin.close()
                stop_at = time.monotonic() + (690 if scenario == "rehearsal" else 100)
                try:
                    while True:
                        with ledger.transaction() as db:
                            current = db.execute("SELECT receipt,state,admitted,started FROM reviews").fetchall()
                        rows.update({row[0]: row[1:] for row in current})
                        states = Counter(row[1] for row in current)
                        maxima["running"] = max(maxima["running"], states["running"])
                        maxima["waiting"] = max(maxima["waiting"], states["reserved"] + states["waiting"])
                        if child.poll() is not None:
                            break
                        if time.monotonic() > stop_at:
                            raise RuntimeError("Browser rehearsal exceeded its time budget")
                        time.sleep(0.1)
                finally:
                    if child.poll() is None:
                        child.terminate()
                        child.wait(timeout=10)
                if child.returncode:
                    raise RuntimeError("The browser rehearsal failed")
                browser = json.load(child.stdout)
        finally:
            server.should_exit = True
            thread.join(10)
    admitted = [row for row in rows.values() if row[1] is not None]
    outcomes = dict(Counter(row[0] for row in admitted))
    maxima["streams"] = streams.maximum
    drained = not streams.active and not any(states[k] for k in ("running", "waiting", "reserved"))
    offered = browser["offered"] + browser.get("direct_seed_count", 0)
    reconciled = (offered == len(admitted) + browser["refused"]
                  and sum(outcomes.get(k, 0) for k in ("completed", "failed", "cancelled", "expired")) == len(admitted)
                  and browser["visible"] + browser.get("direct_seed_count", 0) == outcomes.get("completed", 0))
    passed = (drained and reconciled and browser["failures"] == 0 and max(maxima.values()) <= 2
              and maxima["running"] <= 1 and (scenario == "smoke" or browser["offered"] == 40))
    return {"scenario": scenario, "passed": passed, "drained": drained, "reconciled": reconciled,
            "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "working_tree_modified": bool(subprocess.check_output(["git", "status", "--porcelain"])),
            "python": platform.python_version(), "gradio": gradio.__version__,
            "admitted": len(admitted), "outcomes": outcomes, "observed_maxima": maxima,
            "queue_wait": percentiles([(start - at) * 1000 for _, at, start in admitted if start is not None]),
            "submit_to_visible": percentiles(browser.pop("visible_ms")), "browser": browser}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("smoke", "rehearsal"), default="rehearsal")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="cra2-capacity-") as folder:
        report = run(Path(folder), args.scenario)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
