"""Exercise the seven public C3 cases with a signed synthetic owner in local Chrome."""
import argparse
from contextlib import ExitStack
from datetime import date
from functools import partial, wraps
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import tempfile
import threading
import time
from unittest.mock import patch

from evaluation.answer_packet import Incomplete, bind_capture, digest, require

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "evals/answer-quality/development-v1.json"

# Public presentation checks only. They are applied after delivery.
CHECKS = {
    "public-analogue": ("incident_lookup", ["CX-104", "payment-gateway", "checkout-service", "cross-service", "data/incidents.json#CX-104"]),
    "public-health": ("tool_evidence", ["checkout-service", "Healthy", "freshness", "Verify live", "catalog:checkout-service.status"]),
    "public-ambiguous": ("needs_clarification", ["Which service", "which limit", "current and proposed"]),
    "public-absent": ("no_recovery_record", ["no recovery record", "voucher-worker", "runbook", "tested rollback"]),
    "public-cause": ("ok", ["data/incidents.json#CX-107", "locked writes", "Verify the online option", "not causal proof"]),
    "public-freeze": ("ok", ["The recorded flag is active, and current production status is unknown.",
                             "catalog:auth-service.freeze_window_active", "declaration:summary",
                             "freeze has ended", "Verify current freeze applicability with its owner"]),
    "public-schema": ("ok", ["previous image", "reverse migration", "catalog:inventory-service.rollback",
                             "Direct callers: checkout-service, order-service", "Downstream dependencies to check: None recorded"]),
}


def observed_fields(operation, trace):
    """Project the public case's source fields from the callback invoked by this event."""
    fields = {}
    if operation == "chat":
        for hit in trace["retrieved"]:
            if hit.get("field") == "service":
                fields[hit["chunk_id"] + ".service"] = {"source": hit["source"], "value": hit["text"]}
        for event in trace.get("events", []):
            result = event.get("output", {})
            if "health" in result:
                service = result["service_name"]
                ref = f"catalog:{service}.status"
                if ref in result["evidence"]:
                    fields[service.removesuffix("-service") + ".status"] = {"source": ref, "value": result["health"]}
        return fields
    if trace["status"] != "ok":
        return fields
    for row in trace["history"]["matches"]:
        fields[row["incident_id"] + ".cause"] = {"source": row["evidence_ref"], "value": row["root_cause"]}
    service = trace["service"]
    stem = service.removesuffix("-service")
    rollback = trace["recorded_rollback"]
    fields[stem + ".rollback"] = {"source": rollback["evidence_ref"], "value": rollback["text"]}
    graph = trace["impact"]
    fields[stem + ".calls"] = {"source": graph["source"], "direct": graph["dependencies_to_check"]["direct"]}
    for caller in graph["potential_callers"]["direct"]:
        fields[caller.removesuffix("-service") + ".calls"] = {"source": graph["source"], "calls": service}
    for gap in trace["gaps"]:
        if gap["id"] == "freeze":
            fields[stem + ".freeze"] = {"source": gap["catalog_ref"], "value": gap["recorded_flag"]}
            fields["operator.summary"] = {"source": "declaration:summary", "value": gap["declaration"]}
    return fields


def capture_case(case, origin, assertion, principal, ledger, observed):
    from week2 import incident_rollback
    from week2.session_boundary import session_key

    operation = case["entry_point"]
    cfg = {"origin": origin, "assertion": assertion, "operation": operation, "input": case["input"]}
    proc = subprocess.run(["node", str(Path(__file__).with_name("answer_browser.cjs"))],
                          input=json.dumps(cfg), capture_output=True, text=True, timeout=90)
    if proc.returncode:
        raise RuntimeError(f"Browser failed for {case['id']}: {proc.stderr.replace(assertion, '[withheld]')[:1600]}")
    browser = json.loads(proc.stdout)
    event, session = browser["event"], session_key(principal, browser["session"])
    with ledger.transaction() as db:
        stored = db.execute("SELECT principal,session,operation,state,event_id FROM reviews WHERE delivery=?",
                            (browser["delivery"],)).fetchall()
    session_digest = sha256(session.encode()).hexdigest()
    require(stored == [(ledger.principal_key(principal.key), session_digest, operation, "completed", event)],
            "Visible answer did not match a completed signed session")
    require(event in observed, "Missing guarded callback for the completed delivery")
    client_key, actual_op, actual_input, trace = observed.pop(event)
    expected_input = (case["input"]["message"] if operation == "chat" else
                      [case["input"][k] for k in incident_rollback.FIELDS])
    if operation == "recovery":
        actual_input = list(actual_input)
    require(client_key == principal.key and actual_op == operation and
            browser["submitted"] == actual_input == expected_input, "Submission mismatch")
    status, markers = CHECKS[case["id"]]
    fields = observed_fields(operation, trace)
    rails = {event["stage"]: event["outcome"] for event in trace["rails"]
             if event["engine"] == "nemoguardrails" and event["executed"]}
    required_stages = {"input", "output"}
    if operation == "recovery" or status == "incident_lookup":
        required_stages.add("context")
    checks = {
        "disposition": trace["status"] == status,
        "admission_allowed": trace["admission"]["outcome"] == "allow",
        "provider_unused": trace.get("provider_used") is False and
                           (operation == "recovery" or trace.get("request_attempted") is False),
        "visible_findings": all(m.lower() in browser["text"].lower() for m in markers),
        "source_fields": set(case["sources"]) <= fields.keys(),
        "required_rails": all(rails.get(stage) == "allow" for stage in required_stages),
        "dated_recovery": operation != "recovery" or trace.get("history", {}).get("as_of") == case["as_of"],
    }
    # The browser event/session were independently matched to the capacity ledger and callback.
    submission = {"case_sha256": digest(case), "attempt": "1", "session": stored[0][1], "event": stored[0][4]}
    capture = {"case_sha256": digest(case), "attempt": "1", "session": session_digest, "event": event,
               "answer": browser["text"], "sources": sorted(fields)}
    binding = bind_capture(submission, [capture], fields, digest(CHECKS))
    return {"case": case["id"], "entry_point": operation, "status": trace["status"], "checks": checks,
                 "matched_signed_session": True, "visible_ms": browser["elapsed_ms"], "visible_answer": browser["text"],
                     "observed_fields": fields, "binding": binding, "rail_outcomes": rails,
                     "cache_counts": {k: sum(ev["outcome"] == k for ev in trace.get("cache", [])) for k in ("hit", "miss")},
                 "passed": all(checks.values())}


def collect(root):
    # The child MCP process uses its existing sanitized stdio environment.
    os.environ.update(GRADIO_ANALYTICS_ENABLED="False", NEMO_GUARDRAILS_NO_USAGE_STATS="1",
                      GROQ_API_KEY="", CRA2_RUN_LIVE_TESTS="0", CRA2_LANGSMITH_ENABLED="false",
                      LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false", HF_HUB_OFFLINE="1",
                      TRANSFORMERS_OFFLINE="1", OTEL_SDK_DISABLED="true")
    import httpx
    import uvicorn
    from gradio.context import LocalContext
    from week2 import app, incident_rollback
    from week2.capacity import LocalCapacity, WINDOW_ADMISSIONS, WINDOW_SECONDS
    from week2.cloud_app import create_app
    from week2.iap import IAPKeys, IAPSettings, IAPVerifier
    from week2.tests.test_cloud_storage import ObjectFixture
    from week2.tests.test_iap import AUDIENCE, OWNER, identity, token

    raw = PACKET.read_bytes()
    packet = json.loads(raw)
    cases = packet["cases"]
    for name, filename in (("catalog", "checkout_system.json"), ("incidents", "incidents.json")):
        require(sha256((ROOT / "data" / filename).read_bytes()).hexdigest() == packet["corpus_sha256"][name],
                "Public source version mismatch")
    require(len(cases) == len(CHECKS) and {c["id"] for c in cases} == CHECKS.keys(), "Unexpected schedule")
    dates = {c["as_of"] for c in cases}
    require(len(dates) == 1, "Expected one fixed recovery analysis date")
    as_of = date.fromisoformat(dates.pop())
    keypair = identity.__wrapped__()
    assertion = token(keypair)
    settings = IAPSettings(AUDIENCE, OWNER)
    observed = {}

    def observe(handler, operation):
        @wraps(handler)
        def call(*args, **kwargs):
            result = handler(*args, **kwargs)
            event = LocalContext.event_id.get(None)
            trace = result[-1]
            require(event and event not in observed, "Missing or duplicate callback event")
            observed[event] = (kwargs["client"], operation, args[0], trace)
            return result
        return call

    rows = []
    with ExitStack() as stack:
        jwks = stack.enter_context(httpx.Client(transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"keys": [keypair[1]]}))))
        verifier = IAPVerifier(settings, keys=IAPKeys(client=jwks))
        principal = verifier.verify(assertion)
        require(principal.is_owner and not settings.allowed_emails, "Expected sole fixture owner")
        db_path = root / "private" / "capacity.db"
        ledger = LocalCapacity(db_path)
        stack.enter_context(patch.object(app, "guarded_ui_reply", observe(app.guarded_ui_reply, "chat")))
        stack.enter_context(patch.object(app, "guarded_analyze", observe(app.guarded_analyze, "recovery")))
        stack.enter_context(patch.object(incident_rollback, "analyze", partial(incident_rollback.analyze, as_of=as_of)))
        protected = create_app(settings=settings, verifier=verifier, stores=ObjectFixture(root / "objects.db").stores(),
                               local_capacity_path=db_path)
        sock = stack.enter_context(socket.socket())
        sock.bind(("127.0.0.1", 0))
        origin = f"http://127.0.0.1:{sock.getsockname()[1]}"
        server = uvicorn.Server(uvicorn.Config(protected, access_log=False, log_level="error", proxy_headers=False))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        def stop():
            server.should_exit = True
            thread.join(10)
        stack.callback(stop)
        deadline = time.monotonic() + 20
        while not server.started:
            require(thread.is_alive() and time.monotonic() < deadline, "Local fixture failed to start")
            time.sleep(.05)
        with httpx.Client(base_url=origin, trust_env=False) as client:
            require(client.get("/config").status_code == 401, "Unsigned configuration accessible")
            require(client.get("/config", headers={"x-goog-iap-jwt-assertion": token(
                keypair, sub="other-fixture", email="other@example.test")}).status_code == 403,
                "Uninvited synthetic account admitted")
        next_start = time.monotonic()
        for case in cases:
            time.sleep(max(0, next_start - time.monotonic()))
            try:
                row = capture_case(case, origin, assertion, principal, ledger, observed)
            except (Incomplete, RuntimeError, KeyError, subprocess.TimeoutExpired) as error:
                reason = "Browser timeout" if isinstance(error, subprocess.TimeoutExpired) else str(error)
                row = {"case": case["id"], "entry_point": case["entry_point"], "status": "incomplete",
                       "reason": reason, "passed": False}
            rows.append(row)
            print(row["case"], row["status"], row.get("checks", row.get("reason")), flush=True)
            next_start = time.monotonic() + WINDOW_SECONDS / WINDOW_ADMISSIONS
        unmatched_callbacks = len(observed)
    return {"schema": "c3-public-signed-browser-v1", "scheduled": len(cases), "passed": sum(r["passed"] for r in rows),
            "python": platform.python_version(), "candidate": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "input_sha256": sha256(raw).hexdigest(), "corpus_sha256": packet["corpus_sha256"], "as_of": as_of.isoformat(),
            "access": {"signed_synthetic_owner": True, "unsigned_http": 401, "uninvited_http": 403},
            "unmatched_callbacks": unmatched_callbacks, "independent_pilot": "incomplete", "observations": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(dir="/tmp", prefix="cra2-c3-browser-") as folder:
        report = collect(Path(folder))
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    raise SystemExit(int(report["passed"] != report["scheduled"] or report["unmatched_callbacks"] != 0))
