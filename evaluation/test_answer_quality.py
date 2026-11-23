"""Public C3 calibration and packet-integrity regressions. No human grades."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from evaluation.answer_packet import Incomplete, bind_capture, check_family_splits, digest, verify_binding
from evaluation.answer_quality import load_files, public_report, score, validate


@pytest.fixture
def files():
    return load_files()


def test_hand_counted_packet(files):
    report = public_report(*files)
    assert (report["public_status"], report["matched_controls"], report["scheduled_controls"]) == ("pass", 19, 19)
    assert report["development_cases"] == report["development_families"] == 7
    assert report["fixture_counts"]["pooled"] == {
        "answerable_cases": 15, "asserted_citations": 19, "benign_cases": 19,
        "checkable_claims": 25, "contradicted_claims": 3, "correct_uncertainty_dispositions": 12,
        "critical_contradictions": 3, "critical_items": 42, "critical_omissions": 8,
        "entailed_citations": 18, "false_security_blocks": 1, "missing_attributions": 2,
        "supported_claims": 20, "uncertainty_cases": 14, "unverifiable_claims": 2, "unwarranted_abstentions": 1,
    }
    counts = report["fixture_counts"]
    for metric, total in counts["pooled"].items():
        assert counts["chat"][metric] + counts["recovery"][metric] == total
        assert sum(row[metric] for group, row in counts.items() if group not in {"pooled", "chat", "recovery"}) == total
    assert report["browser_delivery_and_latency"]["samples"] == 0
    assert report["independent_pilot"]["status"] == "incomplete"
    assert report["independent_pilot"]["adjudicated_cases"] == 0


@pytest.mark.parametrize("control,findings", [
    ("grounded-paraphrase", []),
    ("reversed-edge", ["critical_contradiction:reverse-edge"]),
    ("wrong-service", ["critical_contradiction:swapped-service"]),
    ("unsupported-cause", ["unverifiable:certain-cause"]),
    ("invented-live-health", ["unverifiable:live-health"]),
    ("guaranteed-rollback", ["critical_contradiction:guarantee"]),
    ("deleted-caveat", ["critical_omission:migration"]),
    ("hidden-conflict", ["critical_omission:reported-thaw", "critical_omission:resolve-freeze"]),
    ("false-security-block", ["critical_omission:identify-limit", "false_security_block", "wrong_disposition"]),
    ("dependency-unavailable", ["critical_omission:request-evidence", "dependency_unavailable", "wrong_disposition"]),
])
def test_visible_text_changes_produce_specific_findings(files, control, findings):
    packet, key, controls = files
    cases, phrases, _ = validate(*files)
    example = next(r for r in controls["controls"] if r["id"] == control)
    case = cases[example["case_id"]]
    _, actual, _ = score(example["answer"], case["sources"], key["cases"][case["id"]], key, phrases)
    assert actual == sorted(findings)


def test_correct_fact_elsewhere_gets_no_credit(files):
    packet, key, controls = files
    _, phrases, _ = validate(*files)
    text = "The evidence supports a qualified review.\nCX-104 affected payment-gateway. [CX-104.service]"
    _, findings, counts = score(text, [], key["cases"]["public-analogue"], key, phrases)
    assert "unverifiable:payment-record" in findings
    assert counts["supported_claims"] == counts["entailed_citations"] == 0


@pytest.mark.parametrize("change", ["unknown clause", "negation", "broken citation", "blank", "no disposition"])
def test_unrecognized_text_stays_unscored(files, change):
    packet, key, _ = files
    _, phrases, _ = validate(*files)
    additions = {"unknown clause": "\nCheck the cache.", "negation": "\nCheckout does not call inventory.",
                 "broken citation": "\nCheckout calls inventory. [checkout.calls] trailing text"}
    text = "Review follows." + additions.get(change, "")
    if change == "blank":
        text = ""
    if change == "no disposition":
        text = "Checkout calls inventory."
    with pytest.raises(Incomplete):
        score(text, [], key["cases"]["public-schema"], key, phrases)


@pytest.mark.parametrize("change", ["duplicate", "missing mutation", "missing challenge", "leaked key",
                                    "bad source", "future incident", "changed corpus", "changed answer",
                                    "changed rubric", "changed question", "wrong case declaration"])
def test_invalid_packets_cannot_pass(files, change):
    packet, key, examples = files
    cases = packet["cases"]
    if change == "duplicate":
        cases.append(deepcopy(cases[0]))
    elif change == "missing mutation":
        examples["controls"] = [r for r in examples["controls"] if r["id"] != "wrong-service"]
    elif change == "missing challenge":
        cases[0]["challenge"] = cases[1]["challenge"]
    elif change == "leaked key":
        cases[0]["input"]["expected_disposition"] = "qualify"
    elif change == "bad source":
        cases[0]["sources"].append("missing-field")
    elif change == "future incident":
        cases[0]["as_of"] = "2024-01-01"
    elif change == "changed corpus":
        packet["corpus_sha256"]["catalog"] = "stale"
    elif change == "changed answer":
        examples["controls"][0]["answer"] += "\nReview follows."
    elif change == "changed rubric":
        key["cases"]["public-schema"]["benign"] = False
    elif change == "changed question":
        cases[0]["input"]["message"] += " Include another rollout."
    elif change == "wrong case declaration":
        cases[0]["sources"].append("operator.summary")
    with pytest.raises(Incomplete):
        public_report(*files)


def test_mismatch_between_observed_and_expected_fails_the_control(files):
    packet, key, examples = files
    example = next(r for r in examples["controls"] if r["id"] == "wrong-service")
    example["expected_findings"].append("false_security_block")
    report = public_report(*files)
    assert report["public_status"] == "fail"
    assert report["matched_controls"] == 18
    assert report["independent_pilot"]["status"] == "incomplete"


def test_family_overlap_is_rejected():
    check_family_splits(["cx104-family"], [])
    with pytest.raises(Incomplete):
        check_family_splits(["cx104-family"], ["cx104-family"])


@pytest.fixture
def capture():
    submission = {"case_sha256": digest({"id": "public-absent"}), "attempt": "1",
                  "session": "synthetic-session", "event": "synthetic-event"}
    return submission, {**submission, "answer": "There is insufficient evidence.", "sources": []}


@pytest.mark.parametrize("change", ["missing", "duplicate", "session", "event", "attempt", "case_sha256",
                                    "no trace", "unknown ref", "duplicate ref", "empty answer"])
def test_capture_integrity(capture, change):
    submission, row = capture
    attempts = [row]
    if change in {"missing", "duplicate"}:
        attempts = [] if change == "missing" else [row, row]
    elif change in submission:
        row[change] = "wrong"
    elif change == "no trace":
        del row["sources"]
    elif change == "empty answer":
        row["answer"] = " "
    else:
        row["sources"] = ["unknown"] if change == "unknown ref" else ["public-field"] * 2
    with pytest.raises(Incomplete):
        bind_capture(submission, attempts, {"public-field": "bounded fixture"}, "rubric")


def test_binding_distinguishes_empty_trace_from_changed_evidence(capture):
    submission, row = capture
    empty = bind_capture(submission, [row], {}, "rubric")
    verify_binding(empty, digest(empty))
    row["sources"] = ["fact"]
    first = bind_capture(submission, [row], {"fact": "one"}, "rubric")
    second = bind_capture(submission, [row], {"fact": "two"}, "rubric")
    for changed in (empty, second):
        with pytest.raises(Incomplete):
            verify_binding(changed, digest(first))
    assert not (set(first) & {"session", "event", "answer"})


def test_cli_rejects_stale_report(tmp_path):
    path = tmp_path / "report.json"
    baseline = tmp_path / "stale.json"
    baseline.write_text('{"independent_pilot":{"status":"pass"}}')
    result = subprocess.run([sys.executable, "-m", "evaluation.answer_quality", "--verify", str(baseline),
                             "--out", str(path)], cwd=Path(__file__).resolve().parents[1], capture_output=True)
    assert result.returncode != 0
    report = json.loads(path.read_text())
    assert report["public_status"] == report["independent_pilot"]["status"] == "incomplete"
