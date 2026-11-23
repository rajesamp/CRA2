"""Record guarded callback outcomes for the frozen public C3 inputs on local storage."""
import argparse
from collections import Counter
from datetime import date
from functools import partial
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
from unittest.mock import patch

from evaluation import offline


ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "evals/answer-quality/development-v1.json"


def collect():
    os.environ.update(GRADIO_ANALYTICS_ENABLED="False", NEMO_GUARDRAILS_NO_USAGE_STATS="1",
                      GROQ_API_KEY="", CRA2_RUN_LIVE_TESTS="0",
                      LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false", CRA2_LANGSMITH_ENABLED="false")
    from week2 import app, incident_rollback
    from week2.abuse import AbuseGate
    from week2.memory import MemoryStore
    from week2.owner_audit import OwnerAuditStore

    data = INPUTS.read_bytes()
    rows = []
    with tempfile.TemporaryDirectory(dir="/tmp", prefix="cra2-public-callback-") as folder:
        root = Path(folder)
        gate = AbuseGate(store=OwnerAuditStore(root / "audit.sqlite3"))
        for case in json.loads(data)["cases"]:
            case_id, values = case["id"], case["input"]
            if case["entry_point"] == "chat":
                answer, _, trace = app.guarded_ui_reply(
                    values["message"], [], "Local evidence only", case_id, gate=gate, client=case_id,
                    memory_store=MemoryStore(root / case_id / "memory.sqlite3"))
            else:
                # Pin only the recovery engine's as-of date. Admission and NeMo still run.
                as_of = date.fromisoformat(case["as_of"])
                dated_analysis = partial(incident_rollback.analyze, as_of=as_of)
                with patch.object(incident_rollback, "analyze", dated_analysis):
                    answer, trace = incident_rollback.guarded_analyze(
                        [values[k] for k in incident_rollback.FIELDS], gate=gate, client=case_id)
                if trace["status"] == "ok" and trace["history"]["as_of"] != case["as_of"]:
                    raise ValueError("Recovery clock mismatch")
            if not answer.strip() or trace.get("provider_used") or trace.get("request_attempted"):
                raise ValueError("Expected a local callback response")
            admission = trace["admission"]
            rows.append({"case": case_id, "entry_point": case["entry_point"], "callback_status": trace["status"],
                         "admission_code": admission["code"], "admission_outcome": admission["outcome"],
                         "response_sha256": sha256(answer.encode()).hexdigest()})
    if offline.ATTEMPTS:
        raise RuntimeError("Unexpected callback network attempt")
    return {"schema": "c3-public-callbacks-v1", "python": platform.python_version(),
            "app_tree": subprocess.check_output(["git", "rev-parse", "HEAD:week2"], cwd=ROOT, text=True).strip(),
            "input_sha256": sha256(data).hexdigest(), "network_attempts": 0,
            "measurement": "Guarded local callback responses before browser delivery",
            "outcomes": dict(Counter(row["callback_status"] for row in rows)), "observations": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = collect()
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("Observed public callback outcomes", report["outcomes"])
