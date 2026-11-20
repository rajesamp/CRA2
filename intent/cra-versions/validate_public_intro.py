"""Validate the fresh judge's decision against the pinned evidence; render footer."""
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
    raw = (ROOT / "public-intro-v1.pinned.json").read_bytes()
    manifest = json.loads(raw)
    assert raw == (json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    verdict = json.loads((ROOT / "public-intro-v1.judge.json").read_text())
    validate(manifest, verdict)
    invalid = dict(verdict, evidence_ids=[row["id"] for row in manifest["evidence"] if row["type"] == "CAPABILITY"])
    try:
        validate(manifest, invalid)
    except AssertionError:
        pass
    else:
        raise AssertionError("Capability-only evidence accepted as preferred")
    record = {"sha256": hashlib.sha256(raw).hexdigest(), "level": verdict["level"], "delta": "requirement",
              "delta_basis": "User replaced the protected-intro and owner-only presence defaults with a public intro and authenticated shared presence.",
              "prior_hosting_verdict": None, "prior_defaults_revision": "d55862bace1723ebd731ae9a35197df95098f861",
              "verdict": verdict}
    path = ROOT / "public-intro-v1.record.json"
    if path.exists():
        assert json.loads(path.read_text()) == record
    else:
        path.write_text(json.dumps(record, indent=2) + "\n")
    print(f"⟦ verdict · sha256={record['sha256']} · level={record['level']} · delta={record['delta']} ⟧")
