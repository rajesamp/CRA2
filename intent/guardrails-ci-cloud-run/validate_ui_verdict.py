"""Validate the fresh UI judge against the immutable manifest and prior plan."""
import hashlib
import json
from pathlib import Path
import subprocess

from validate_verdict import validate


ROOT = Path(__file__).resolve().parent


if __name__ == "__main__":
    raw = (ROOT / "ui-framework.pinned.json").read_bytes()
    manifest = json.loads(raw)
    assert raw == (json.dumps(manifest, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False) + "\n").encode()
    digest = hashlib.sha256(raw).hexdigest()
    verdict = json.loads((ROOT / "ui-framework.judge.json").read_text())
    # Preserve the judge output verbatim; phrase validation is case-insensitive.
    checked = dict(verdict, rationale=verdict["rationale"].lower())
    validate(manifest, checked)
    try:
        validate(manifest, dict(checked, level="preferred", winner_established=True))
    except AssertionError:
        pass
    else:
        raise AssertionError("Capability evidence accepted as comparative preference")

    baseline = json.loads((ROOT / "ui-framework.baseline.json").read_text())
    prior = subprocess.check_output(
        ["git", "show", baseline["source_revision"] + ":" + baseline["source"]],
        cwd=ROOT,
    )
    assert hashlib.sha256(prior).hexdigest() == baseline["sha256"]
    prior_options = {name for name in ("gradio", "streamlit")
                     if name in prior.decode().lower()}
    assert prior_options == set(baseline["planned_options"])
    added = {option["id"] for option in manifest["options"]} - prior_options
    assert added == {"streamlit"}
    record = {
        "sha256": digest, "level": verdict["level"], "delta": "option_added",
        "delta_basis": "Streamlit added to the earlier Gradio-only delivery plan; the earlier comparison was incomplete.",
        "previous_plan_revision": baseline["source_revision"],
        "previous_framework_verdict": None,
        "scope_note": "First validated UI-framework comparison; earlier access-architecture verdicts are separate.",
        "verdict": verdict,
    }
    target = ROOT / "ui-framework.record.json"
    if target.exists():
        assert json.loads(target.read_text()) == record, "Pin a new revision for material changes"
    else:
        target.write_text(json.dumps(record, indent=2) + "\n")
    print(f"⟦ verdict · sha256={digest} · level={record['level']} · delta={record['delta']} ⟧")
