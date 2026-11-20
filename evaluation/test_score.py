"""Negative controls prove the CI gate cannot pass missing or broken evidence."""
import hashlib
import json
import socket

import pytest

from evaluation import score
from evaluation.offline import ATTEMPTS


def collected():
    manifest = json.loads(score.CASES.read_text())
    return {"schema": 1, "cases_sha256": hashlib.sha256(score.CASES.read_bytes()).hexdigest(),
            "network_attempts": 0, "corpus_digest": "synthetic-test", "source_commit": "test",
            "encoder_fingerprint": "synthetic-test", "collector_sha256": "test",
            "cases": [{"id": c["id"], "retrieved_ids": c["reference_ids"], "chunk_count": 2}
                      for c in manifest["cases"]]}


def test_real_metrics_and_controls_accept_perfect_and_reject_irrelevant_runs():
    data = collected()
    result = score.evaluate(data)
    assert result["passed"] and result["mean"] == {"precision": 1., "recall": 1.}
    assert len(result["controls"]) == 7 and all(c["passed"] for c in result["controls"])
    assert result["provider_attempts"] == result["network_attempts"] == 0
    for case in data["cases"]:
        case["retrieved_ids"] = ["irrelevant"]
    result = score.evaluate(data)
    assert not result["passed"] and result["mean"] == {"precision": 0., "recall": 0.}


@pytest.mark.parametrize("fault", ["missing", "duplicate", "foreign", "wrong_labels", "egress", "empty", "too_many_chunks"])
def test_incomplete_or_unverified_runs_fail_closed(fault):
    data = collected()
    if fault == "missing": data["cases"].pop()
    if fault == "duplicate": data["cases"][-1] = data["cases"][0]
    if fault == "foreign": data["cases"][0]["id"] = "unknown"
    if fault == "wrong_labels": data["cases_sha256"] = "wrong"
    if fault == "egress": data["network_attempts"] = 1
    if fault == "empty": data["cases"][0]["retrieved_ids"] = []
    if fault == "too_many_chunks": data["cases"][0]["chunk_count"] = 100
    with pytest.raises(ValueError):
        score.evaluate(data)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -.1, 1.1])
def test_missing_or_impossible_metric_cannot_be_averaged_away(monkeypatch, bad):
    monkeypatch.setattr(score.GroundTruthAgreement, "recall_at_k", lambda *a, **k: bad)
    with pytest.raises(ValueError, match="Unavailable or invalid"):
        score.metrics(["a"], ["a"])


def test_offline_boundary_blocks_even_if_a_library_catches_the_network_error():
    try:
        with pytest.raises(RuntimeError, match="egress"):
            socket.getaddrinfo("example.invalid", 443)
        assert ATTEMPTS
        with pytest.raises(ValueError, match="network/provider"):
            score.metrics(["a"], ["a"])
    finally:
        ATTEMPTS.clear()


def test_provider_is_explicitly_forbidden():
    try:
        with pytest.raises(RuntimeError, match="LLM evaluation"):
            score.ForbiddenProvider(model_engine="offline-forbidden")._create_chat_completion()
        with pytest.raises(ValueError, match="network/provider"):
            score.metrics(["a"], ["a"])
    finally:
        score.PROVIDER_ATTEMPTS.clear()
