"""Real TruLens ID-retrieval metrics with fail-closed gates and scorer controls."""
from evaluation.offline import ATTEMPTS

import argparse
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path

from trulens.feedback import GroundTruthAgreement
from trulens.feedback.llm_provider import LLMProvider

ROOT = Path(__file__).resolve().parent
CASES = ROOT / "retrieval-cases-v1.json"
PROVIDER_ATTEMPTS = []


class ForbiddenProvider(LLMProvider):
    """Avoid TruLens' default OpenAI provider; no semantic judge is configured."""
    def _create_chat_completion(self, *args, **kwargs):
        PROVIDER_ATTEMPTS.append("forbidden")
        raise RuntimeError("LLM evaluation is disabled")


def ids(values, *, nonempty=True):
    if (not isinstance(values, list) or (nonempty and not values) or len(values) > 20
            or any(not isinstance(x, str) or not x or len(x) > 200 for x in values)
            or len(set(values)) != len(values)):
        raise ValueError("Invalid retrieval evaluation IDs")
    return values


def metrics(retrieved, reference):
    ids(retrieved); ids(reference)
    metric = GroundTruthAgreement(
        [{"query": "case", "expected_chunks": [{"text": x, "expect_score": 1} for x in reference]}],
        provider=ForbiddenProvider(model_engine="offline-forbidden"))
    values = {"precision": float(metric.precision_at_k("case", retrieved)),
              "recall": float(metric.recall_at_k("case", retrieved))}
    if any(not math.isfinite(v) or not 0 <= v <= 1 for v in values.values()):
        raise ValueError("Unavailable or invalid metric")
    if ATTEMPTS or PROVIDER_ATTEMPTS:
        raise ValueError("Unexpected evaluation network/provider attempt")
    return values


def controls():
    rows = []
    for label, retrieved, expected in [("perfect", ["a", "b"], 1.),
                                       ("partial", ["a", "x"], .5), ("miss", ["x", "y"], 0.)]:
        score = metrics(retrieved, ["a", "b"])
        rows.append({"id": label, "passed": score == {"precision": expected, "recall": expected}})
    for label, retrieved, reference in [("empty_retrieval", [], ["a"]), ("empty_reference", ["a"], []),
                                         ("duplicate_ids", ["a", "a"], ["a"]), ("invalid_id", [None], ["a"])]:
        try:
            metrics(retrieved, reference)
        except ValueError:
            rejected = True
        else:
            rejected = False
        rows.append({"id": label, "passed": rejected})
    return rows


def evaluate(collected):
    manifest = json.loads(CASES.read_text())
    if (collected.get("schema") != 1 or collected.get("cases_sha256") != hashlib.sha256(CASES.read_bytes()).hexdigest()
            or collected.get("network_attempts") != 0):
        raise ValueError("Unverified retrieval run")
    expected = {c["id"]: c for c in manifest["cases"]}
    cases = collected.get("cases")
    if (not isinstance(cases, list) or len(cases) != manifest["gates"]["expected_cases"]
            or len({c["id"] for c in cases}) != len(cases) or {c["id"] for c in cases} != set(expected)):
        raise ValueError("Incomplete or duplicated evaluation cases")
    rows = []
    for case in cases:
        reference = expected[case["id"]]["reference_ids"]
        if not len(case["retrieved_ids"]) <= case["chunk_count"] <= manifest["k_chunks"]:
            raise ValueError("Invalid retrieval denominator")
        score = metrics(case["retrieved_ids"], reference)
        rows.append({"id": case["id"], **score, "retrieved_count": len(case["retrieved_ids"]),
                     "reference_count": len(reference), "passed": score["recall"] >= manifest["gates"]["min_each_recall"]})
    mean = {m: sum(c[m] for c in rows) / len(rows) for m in ("precision", "recall")}
    canaries = controls()
    passed = (all(c["passed"] for c in rows + canaries)
              and mean["precision"] >= manifest["gates"]["min_mean_precision"]
              and mean["recall"] >= manifest["gates"]["min_mean_recall"])
    return {"framework": "trulens-feedback", "version": version("trulens-feedback"), "passed": passed,
            "cases_sha256": collected["cases_sha256"], "corpus_digest": collected["corpus_digest"],
            "source_commit": collected["source_commit"], "encoder_fingerprint": collected["encoder_fingerprint"],
            "collector_sha256": collected["collector_sha256"], "scorer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "environment_lock_sha256": hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest(),
            "network_attempts": len(ATTEMPTS), "provider_attempts": len(PROVIDER_ATTEMPTS),
            "case_count": len(rows), "mean": mean, "cases": rows, "controls": canaries,
            "gates": manifest["gates"], "label_basis": manifest["label_basis"],
            "semantic_faithfulness": "not_measured", "jailbreak_resistance": "not_measured"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    report = evaluate(json.loads(args.input.read_text()))
    args.out.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: report[k] for k in ("framework", "version", "passed", "case_count", "mean")}))
    raise SystemExit(0 if report["passed"] else 1)
