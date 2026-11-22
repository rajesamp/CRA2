"""Validate the independent verdict against immutable Stage 1 evidence."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def validate(manifest, verdict):
    assert verdict["option_id"] in {row["id"] for row in manifest["options"]}
    assert verdict["level"] in {"possible", "suitable", "preferred"}
    evidence = {row["id"]: row for row in manifest["evidence"]}
    assert verdict["evidence_ids"] and set(verdict["evidence_ids"]) <= evidence.keys()
    if verdict["level"] == "preferred":
        top = manifest["priority_order"][0]
        assert any(evidence[key]["type"] == "COMPARATIVE" and top in evidence[key]["criteria"]
                   for key in verdict["evidence_ids"])
        assert not any(row["status"] == "UNKNOWN" and top in row["criteria"] for row in manifest["requirements"])
        assert verdict["winner_established"] is True
    else:
        assert verdict["winner_established"] is False
        assert "winner not established" in verdict["rationale"].lower() and verdict["separating_test"]


if __name__ == "__main__":
    raw = (ROOT / "sequence-v1.pinned.json").read_bytes()
    manifest = json.loads(raw)
    assert raw == (json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    for name, digest in manifest["artifact_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    verdict = json.loads((ROOT / "sequence-v1.judge.json").read_text())
    validate(manifest, verdict)
    invalid = dict(verdict, level="preferred", winner_established=True,
                   evidence_ids=[row["id"] for row in manifest["evidence"] if row["type"] == "CAPABILITY"])
    try:
        validate(manifest, invalid)
    except AssertionError:
        pass
    else:
        raise AssertionError("Capability-only preference accepted")
    record = {"sha256": hashlib.sha256(raw).hexdigest(), "level": verdict["level"],
              "delta": "requirement", "prior_verdict": None,
              "delta_basis": "User requested SDLC corrections and feature prioritization; separate from the existing evaluation-framework decision.",
              "verdict": verdict}
    path = ROOT / "sequence-v1.record.json"
    if path.exists():
        assert json.loads(path.read_text()) == record
    else:
        path.write_text(json.dumps(record, indent=2) + "\n")
    print(f"⟦ verdict · sha256={record['sha256']} · level={record['level']} · delta={record['delta']} ⟧")
