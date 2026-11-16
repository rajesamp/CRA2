"""A broken/empty/stale scanner report must never look like a clean image."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from scripts.scan_container import validate_evidence

IMAGE = "sha256:" + "a" * 64


def reports():
    packages = [dict(id=str(i), name=name, version="test", type="python")
                for i, name in enumerate(("gradio", "fastembed", "nemoguardrails", "pyjwt"))]
    sbom = {"descriptor": {"name": "syft", "version": "1.57.2"}, "artifacts": packages,
        "source": {"type": "image", "metadata": {"imageID": IMAGE}}, "distro": {"id": "debian"}}
    scan = {"descriptor": {"name": "grype", "version": "0.122.0",
        "configuration": {"only-fixed": False, "only-notfixed": False, "exclude": [], "ignore-wontfix": ""},
        "db": {"status": {"valid": True, "built": datetime.now(timezone.utc).isoformat()}}},
        "source": {"type": "image", "target": {"imageID": IMAGE}}, "matches": []}
    return sbom, scan


def test_valid_complete_clean_report_passes():
    sbom, scan = reports()
    result = validate_evidence(sbom, scan, IMAGE)
    assert result["status"] == "passed" and result["packages_examined"] == 4


@pytest.mark.parametrize("mutation", ["empty", "missing-package", "wrong-image", "invalid-db", "stale-db", "filtered", "missing-matches"])
def test_collection_failures_are_errors_not_clean_results(mutation):
    sbom, scan = reports()
    if mutation == "empty":sbom["artifacts"] = []
    elif mutation == "missing-package":sbom["artifacts"].pop()
    elif mutation == "wrong-image":scan["source"]["target"]["imageID"] = "sha256:" + "b" * 64
    elif mutation == "invalid-db":scan["descriptor"]["db"]["status"]["valid"] = False
    elif mutation == "stale-db":scan["descriptor"]["db"]["status"]["built"] = "2020-01-01T00:00:00Z"
    elif mutation == "filtered":scan["descriptor"]["configuration"]["only-fixed"] = True
    elif mutation == "missing-matches":del scan["matches"]
    with pytest.raises(ValueError):validate_evidence(sbom, scan, IMAGE)


@pytest.mark.parametrize("severity", ["High", "Critical", "Unknown"])
def test_high_or_unrated_findings_block_release(severity):
    sbom, scan = reports()
    scan["matches"] = [{"artifact": deepcopy(sbom["artifacts"][0]),
                        "vulnerability": {"id": "synthetic-vulnerability", "severity": severity,
                                          "fix": {"versions": [], "state": "not-fixed"}}}]
    result = validate_evidence(sbom, scan, IMAGE)
    assert result["status"] == "blocked" and len(result["blocking_findings"]) == 1
