"""Reproducible synthetic evaluation; validation selects, held-out test reports."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from week1.retrieval import MODEL_NAME, _encoder_identity
from week2.abuse import AbuseClassifier, EXAMPLES, MIN_MARGIN, MIN_SIMILARITY, prohibited_request


def metrics(rows, predictions):
    tp = sum(row["label"] == "adversarial" and prediction for row, prediction in zip(rows, predictions))
    fp = sum(row["label"] == "benign" and prediction for row, prediction in zip(rows, predictions))
    fn = sum(row["label"] == "adversarial" and not prediction for row, prediction in zip(rows, predictions))
    tn = sum(row["label"] == "benign" and not prediction for row, prediction in zip(rows, predictions))
    return {"examined": len(rows), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": tp / (tp + fp) if tp + fp else 0,
            "recall": tp / (tp + fn) if tp + fn else 0,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0,
            "accuracy": (tp + tn) / len(rows)}


def evaluate():
    classifier = AbuseClassifier()
    validation = [row for row in classifier.rows if row["split"] == "validation"]
    validation_scores = [classifier.scores(row["text"]) for row in validation]
    candidates = []
    for margin in (0, .02, .035, .05, .08):
        predicted = [score["attack_similarity"] >= MIN_SIMILARITY and score["margin"] >= margin for score in validation_scores]
        candidates.append({"margin": margin, **metrics(validation, predicted)})
    selected = max(candidates, key=lambda item: (item["f1"], -item["fp"], -item["margin"]))
    if selected["margin"] != MIN_MARGIN:
        raise ValueError("Validation no longer supports the configured threshold")
    test = [row for row in classifier.rows if row["split"] == "test"]
    # Test examples are first featurized only after the validation decision.
    test_scores = [classifier.scores(row["text"]) for row in test]
    predicted = [score["attack_similarity"] >= MIN_SIMILARITY and score["margin"] >= MIN_MARGIN for score in test_scores]
    return {"executed_at": datetime.now(timezone.utc).isoformat(), "model": MODEL_NAME,
            "encoder_fingerprint": _encoder_identity(classifier.encoder),
            "examples_sha256": hashlib.sha256(EXAMPLES.read_bytes()).hexdigest(),
            "splits": {split: sum(row["split"] == split for row in classifier.rows) for split in ("train", "validation", "test")},
            "missing_labels": 0, "duplicate_texts": len(classifier.rows) - len({row["text"] for row in classifier.rows}),
            "validation_candidates": candidates, "selected_margin": MIN_MARGIN, "minimum_similarity": MIN_SIMILARITY,
            "test_majority_baseline": metrics(test, [False] * len(test)),
            "test_nearest_prototype_baseline": metrics(test, [score["margin"] >= 0 for score in test_scores]),
            "test_configured_classifier": metrics(test, predicted),
            "test_replay_combined_guard": metrics(test, [guess or prohibited_request(row["text"]) for row, guess in zip(test, predicted)]),
            "combined_replay_is_not_an_unseen_test": True,
            "test_errors": [{"id": row["id"], "expected": row["label"], "predicted": "adversarial" if guess else "benign"}
                            for row, guess in zip(test, predicted) if (row["label"] == "adversarial") != guess],
            "limitations": "Small synthetic English examples; uncalibrated similarity; no proof of intent or coverage of encoded, multilingual, multi-turn or novel attacks. Runtime audit records never enter training."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = evaluate()
    encoded = json.dumps(report, indent=2, allow_nan=False)
    if args.out:
        root = Path(__file__).resolve().parents[1]
        path = args.out.resolve()
        if not any(path.is_relative_to(folder) for folder in (root, Path('/tmp').resolve())):
            parser.error("Output must stay in CRA2 or /tmp")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
