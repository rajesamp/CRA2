"""Run the capacity rehearsal against a temporary loopback app and synthetic IAP identities."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import platform
import secrets
import socket
import sqlite3
import subprocess
import tempfile
import threading
import time

import gradio
from gradio.context import LocalContext
import httpx
from starlette.datastructures import MutableHeaders
from starlette.responses import Response
import uvicorn

from week2.capacity import LocalCapacity, MAX_OUTSTANDING, MAX_WAITING, RUN_SECONDS, WAIT_SECONDS, WINDOW_ADMISSIONS, WINDOW_SECONDS
from week2.cloud_app import create_app
from week2.welcome import EXAMPLE
from week2.iap import IAPKeys, IAPSettings, IAPVerifier
from week2.session_boundary import session_key
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
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    modified = bool(subprocess.check_output(["git", "status", "--porcelain"]))
    keypair = identity.__wrapped__()
    member = "second@example.test"
    settings = IAPSettings(AUDIENCE, OWNER, (member,))
    keys = IAPKeys(client=httpx.Client(transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json={"keys": [keypair[1]]}))))
    db_path = root / "private" / "capacity.db"
    verifier = IAPVerifier(settings, keys=keys)
    stores = ObjectFixture(root / "fixture.db").stores()
    actual_write = stores.telemetry.write
    trace_ids = {}

    def observe_write(trace):
        actual_write(trace)
        event = LocalContext.event_id.get(None)
        if event:
            trace_ids[event] = trace["request_id"]

    stores.telemetry.write = observe_write
    protected = create_app(settings=settings, verifier=verifier, stores=stores, local_capacity_path=db_path)
    ledger = LocalCapacity(db_path)
    response_counts = Counter()
    identities = {secrets.token_hex(32): (email, f"local-reviewer-{i}") for i, email in enumerate((OWNER, member))}
    principals = {i: verifier.verify(token(keypair, email=email, sub=subject))
                  for i, (email, subject) in enumerate(identities.values(), 1)}
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
                async def observed(message):
                    if message["type"] == "http.response.start" and scope["path"].startswith("/gradio_api/"):
                        route = scope["path"].split("/")[2]
                        response_counts[f"{route} {message['status']}"] += 1
                    await send(message)
                return await protected(scope, receive, observed)
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
        events = {}
        maxima = {"running": 0, "waiting": 0}
        try:
            # Per-submission observations can exceed a pipe buffer before the child exits.
            with (tempfile.TemporaryFile(mode="w+", encoding="utf-8") as output,
                  subprocess.Popen(["node", str(driver)], stdin=subprocess.PIPE, stdout=output, text=True) as child):
                child.stdin.write(json.dumps({"origin": f"http://{host}", "identities": list(identities),
                                              "scenario": scenario, "chat_prompt": EXAMPLE}))
                child.stdin.close()
                stop_at = time.monotonic() + (690 if scenario == "rehearsal" else 100)
                try:
                    while True:
                        with ledger.transaction() as db:
                            current = db.execute("SELECT receipt,state,admitted,started,event_id,principal,session,operation "
                                                 "FROM reviews").fetchall()
                        for receipt, state, admitted_at, started_at, event, principal, session, operation in current:
                            rows[receipt] = (state, admitted_at, started_at)
                            if event:
                                events[event] = (principal, session, operation, state)
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
                output.seek(0)
                browser = json.load(output)
        finally:
            server.should_exit = True
            thread.join(10)
    admitted = [row for row in rows.values() if row[1] is not None]
    outcomes = dict(Counter(row[0] for row in admitted))
    maxima["streams"] = streams.maximum
    with sqlite3.connect(root / "fixture.db") as fixture_db:
        telemetry = [json.loads(raw) for raw, in fixture_db.execute(
            "SELECT body FROM objects WHERE name LIKE 'telemetry/v1/%'")]
    chat_evidence = {"outcomes": dict(Counter(record["status"] for record in telemetry)),
                     "tool_attempts": sum(record["mcp"].get("attempted") or 0 for record in telemetry),
                     "tool_failures": sum(record["mcp"].get("failed") or 0 for record in telemetry),
                     "provider_attempts": sum(record["provider_attempted"] for record in telemetry)}
    by_id = {record["request_id"]: record for record in telemetry}
    matched_events = set()
    checked = Counter()
    for observation in sorted(browser["observations"], key=lambda item: item["submission"]):
        event = observation.pop("event")
        principal = principals[observation["user"]]
        session = session_key(principal, observation.pop("session"))
        operation = observation["operation"]
        expected = (ledger.principal_key(principal.key), sha256(session.encode()).hexdigest(), operation, "completed")
        observation["matched_session_completion"] = event not in matched_events and events.get(event) == expected
        matched_events.add(event)
        if operation == "chat":
            record = by_id.get(trace_ids.get(event), {})
            stages = {span["stage"] for span in record.get("spans", []) if span["outcome"] == "completed"}
            observation["matched_local_evidence"] = (record.get("status") == "evidence_only"
                and record.get("provider_attempted") is False and {"retrieve", "tools"} <= stages)
            observation["cache"] = record.get("cache_counts", {})
        if observation["matched_session_completion"] and observation.get("matched_local_evidence", True):
            checked[(observation["user"], operation)] += 1
    browser["observations"].sort(key=lambda item: item["submission"])
    fully_observed = (sum(checked.values()) == browser["visible"] and
        (scenario == "smoke" or all(checked[user, op] == 10 for user in principals for op in ("chat", "recovery"))))
    drained = not streams.active and not any(states[k] for k in ("running", "waiting", "reserved"))
    offered = browser["offered"] + browser.get("direct_seed_count", 0)
    reconciled = (offered == len(admitted) + browser["refused"]
                  and sum(outcomes.get(k, 0) for k in ("completed", "failed", "cancelled", "expired")) == len(admitted)
                  and browser["visible"] + browser.get("direct_seed_count", 0) == outcomes.get("completed", 0))
    passed = (drained and reconciled and fully_observed and browser["visible"] > 0 and browser["failures"] == 0
              and chat_evidence["outcomes"].get("evidence_only", 0) == browser["visible_by_operation"]["chat"]
              and chat_evidence["tool_attempts"] > 0 and chat_evidence["tool_failures"] == chat_evidence["provider_attempts"] == 0
              and maxima["streams"] <= 2 and maxima["waiting"] <= MAX_WAITING and maxima["running"] <= 1
              and (scenario == "smoke" or browser["operations"] == {"chat": 20, "recovery": 20}))
    return {"scenario": scenario, "passed": passed, "drained": drained, "reconciled": reconciled,
            "revision": revision, "working_tree_modified": modified, "synthetic_principals": 2,
            "limits": {"running":1, "waiting":MAX_WAITING, "outstanding_per_principal":MAX_OUTSTANDING,
                       "admissions_per_window":WINDOW_ADMISSIONS, "window_s":WINDOW_SECONDS,
                       "wait_s":WAIT_SECONDS, "run_s":RUN_SECONDS, "streams":2, "idle_stream_s":streams.idle,
                       "reconnect_grace_s":streams.grace, "reconnects_per_minute":4},
            "python": platform.python_version(), "gradio": gradio.__version__,
            "admitted": len(admitted), "outcomes": outcomes, "observed_maxima": maxima,
            "http_responses": dict(response_counts), "chat_evidence": chat_evidence,
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
