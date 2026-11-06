"""P0 offline baseline; compare observation on/off, not unimplemented SAC modes.

Run with the locked Week 2 environment. Fixtures replace retrieval and MCP
transport; the actual bounded read-only tool functions and graph are exercised.
There is deliberately no live-provider switch or estimate of model savings.
"""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from time import perf_counter
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cra2.advisor import ADVISORY
from week1 import chat
from week2 import tools, workflow
from week2.contracts import NAMES
from week2.memory import MemoryStore

DATASET = ROOT / "evals/sac-baseline.json"


def digest(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def source_metadata():
    # Include uncommitted implementation bytes, not just a misleading HEAD SHA.
    paths = set(git("ls-files").splitlines()) | set(
        git("ls-files", "--others", "--exclude-standard").splitlines())
    included = sorted(p for p in paths if not p.startswith("docs/evidence/")
                      and Path(p).suffix in {".py", ".json", ".toml", ".lock"})
    sources = {p: digest((ROOT / p).read_bytes()) for p in included
               if (ROOT / p).is_file()}
    return {"git_sha": git("rev-parse", "HEAD"),
            "working_tree_dirty": bool(git("status", "--porcelain")),
            "source_digest": digest(canonical(sources).encode()),
            "source_file_count": len(sources), "source_files": sources}


def percentile(values, quantile):
    """Nearest-rank percentile; meaningful only within this small local sample."""
    return sorted(values)[max(0, math.ceil(len(values) * quantile) - 1)]


def _normalized(answer, trace):
    return {"answer": answer, "trace": {k: v for k, v in trace.items()
                                       if k not in {"request_id", "session_id"}}}


def run_benchmark(*, repeat=5, dataset=DATASET):
    if os.environ.get("CRA2_CONTEXT_MODE") is not None:
        raise ValueError("Unset CRA2_CONTEXT_MODE before running the legacy P0 baseline")
    if type(repeat) is not int or not 1 <= repeat <= 100:
        raise ValueError("repeat must be between 1 and 100")
    raw = Path(dataset).read_bytes()
    fixtures = json.loads(raw)
    configuration = {"mode": "Local evidence only", "context_mode": "baseline",
        "provider": None, "model": None, "seed": fixtures["seed"],
        "provider_settings": None, "repeat": repeat,
        "retrieval": "fixed-synthetic-fixture", "tool_transport": "in-process",
        "memory": "isolated-empty", "pair_order": "alternating",
        # Import-time settings can originate outside this checkout. Bind the
        # actual loaded authorities without exposing their values or paths.
        "loaded_inputs_sha256": {
            name: digest(canonical(value).encode()) for name, value in (
                ("team_settings", chat.TEAM_SETTINGS), ("catalog", chat.CATALOG),
                ("rules", chat.RULES),
            )}}
    samples, stable, failures = [], {}, []
    functions = dict(zip(NAMES, (tools.check_system_health, tools.get_dependency_graph)))

    def no_provider(*_args, **_kwargs):
        raise AssertionError("Offline benchmark cannot call a provider")

    with tempfile.TemporaryDirectory(prefix="cra2-sac-", dir="/tmp") as temporary:
        for iteration in range(repeat):
            for case in fixtures["cases"]:
                async def tool_runner(calls):
                    if case.get("tool_failure"):
                        return {"status": "error", "outputs": {}, "events": [
                            {"event": "mcp_failed", "code": "timeout"}]}
                    outputs = {name: functions[name](**arguments) for name, arguments in calls}
                    return {"status": "ok", "outputs": outputs, "events": [
                        {"event": "tool_result", "tool": name, "status": result["status"]}
                        for name, result in outputs.items()]}

                pair = {}
                for observed in ((False, True) if iteration % 2 == 0 else (True, False)):
                    events = []
                    started = perf_counter()
                    answer, trace = workflow.respond(case["question"],
                        mode=configuration["mode"],
                        retriever=lambda *_a, **_k: deepcopy(fixtures["hits"]),
                        reviewer=no_provider, tool_runner=tool_runner,
                        memory_store=MemoryStore(Path(temporary) / "empty.sqlite3"),
                        observer=events.append if observed else None)
                    elapsed = (perf_counter() - started) * 1000
                    normalized = _normalized(answer, trace)
                    pair[observed] = normalized
                    fingerprint = digest(canonical(normalized).encode())
                    key = case["id"]
                    stable.setdefault(key, fingerprint)
                    checks = {"expected_status": trace["status"] == case["status"],
                        "repeatable": stable[key] == fingerprint,
                        "advisory_boundary": answer.endswith(ADVISORY),
                        "no_provider_request": not trace.get("request_attempted", False)
                            and not any(e["kind"] == "provider" for e in events)}
                    if not all(checks.values()):
                        failures.append({"case_id": key, "iteration": iteration, "checks": checks})
                    samples.append({"case_id": key, "iteration": iteration,
                        "observed": observed, "latency_ms": elapsed,
                        "status": trace["status"], "output_digest": fingerprint,
                        "checks": checks, "events": events,
                        "action_count": len([e for e in events if e["kind"] == "action"]) if observed else None,
                        "tool_calls": sum(e.get("tool_calls", 0) for e in events) if observed else None,
                        "provider_requests": 0, "input_tokens": None,
                        "output_tokens": None, "usage_status": "not_applicable_local",
                        "risk_level": trace.get("assessment", {}).get("risk_level")})
                if pair[False] != pair[True]:
                    failures.append({"case_id": case["id"], "iteration": iteration,
                                     "checks": {"observer_parity": False}})
    latencies = {str(observed).lower(): [s["latency_ms"] for s in samples
                                        if s["observed"] == observed]
                 for observed in (False, True)}
    return {"schema_version": 1, "run_id": uuid4().hex,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": source_metadata(), "python_version": platform.python_version(),
        "dataset": {"version": fixtures["version"], "sha256": digest(raw),
                    "case_count": len(fixtures["cases"])},
        "configuration": configuration,
        "configuration_sha256": digest(canonical(configuration).encode()),
        "comparison": "baseline-observer-off-vs-on",
        "limitations": ["No SAC/threshold context execution (P2 pending).",
            "No provider calls, token/cost savings or quality parity measured.",
            "Retrieval is a fixed synthetic fixture; MCP transport is bypassed.",
            "Node completion is distinct from a guarded workflow failure status.",
            "Nested node/provider wall times must not be summed.",
            "Latency reflects this local process, not production/provider performance."],
        "summary": {"sample_count": len(samples), "pair_count": len(samples) // 2,
            "failure_count": len(failures), "latency_ms": {
                label: {"p50": percentile(values, .50), "p95": percentile(values, .95)}
                for label, values in latencies.items()},
            "compaction_overhead_ms": None, "peak_context_tokens": None,
            "cost": None, "risk_agreement": None},
        "failures": failures, "samples": samples}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--out", type=Path, required=True,
                        help="New JSON report path; existing evidence is never overwritten")
    args = parser.parse_args()
    report = run_benchmark(repeat=args.repeat)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(f"{report['summary']['pair_count']} pairs; {report['summary']['failure_count']} failures; {args.out}")
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
