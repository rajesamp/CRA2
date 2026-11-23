"""Release identity belongs to the tested source, evidence bytes and observed image."""
from pathlib import Path
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "a" * 40
AT = "2026-11-23T12:00:00Z"


def test_verifier_rejects_another_source():
    from scripts import release_record as release
    identity = release.identity(ROOT, SOURCE, AT)
    with pytest.raises(ValueError, match="source"):
        release.verify_identity(identity, ROOT, "b" * 40)


def test_changed_catalog_cannot_reuse_recorded_dataset(tmp_path):
    from scripts import release_record as release
    original = release.identity(ROOT, SOURCE, AT)
    for filename in original["dataset_inputs"]:
        target = tmp_path / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / filename, target)
    catalog = tmp_path / "data/checkout_system.json"
    catalog.write_bytes(catalog.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="dataset"):
        release.verify_dataset(original, tmp_path)


def test_green_hosted_run_cannot_imply_serving_or_owner_acceptance():
    from scripts import release_record as release
    identity = release.identity(ROOT, SOURCE, AT)
    hosted = {"at": AT, "head": SOURCE, "checkout": "b" * 40, "result": "passed",
              "run": 123, "workflow": "week2-4", "tests": 540}
    record = release.assemble(identity, hosted=hosted)
    assert record["hosted"]["result"] == "passed"
    assert record["serving"]["result"] == "unknown"
    assert record["acceptance"]["result"] == "pending"
