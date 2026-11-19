"""Collect an image SBOM and fail closed on incomplete or blocking scan evidence."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

LOCK = Path(__file__).with_name("supply-chain-tools.json")
REQUIRED = {"gradio", "fastembed", "nemoguardrails", "pyjwt"}
BLOCKING = {"High", "Critical", "Unknown"}
SEVERITIES = BLOCKING | {"Negligible", "Low", "Medium"}


def image_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"(?:sha256:)?[a-f0-9]{64}", value):
        raise ValueError("Missing or invalid immutable image ID")
    return "sha256:" + value.removeprefix("sha256:")


def scan_findings(scan):
    if not isinstance(scan.get("matches"), list) or not isinstance(scan.get("ignoredMatches", []), list):
        raise ValueError("Missing scanner match inventory")
    # Suppressed findings count too: neither tool defaults nor local exceptions
    # may silently turn a blocking finding into a passing release.
    findings = scan["matches"] + scan.get("ignoredMatches", [])
    for match in findings:
        try:
            vulnerability, artifact = match["vulnerability"], match["artifact"]
            if vulnerability["severity"] not in SEVERITIES:
                raise ValueError("Unrecognized severity")
            if not all(isinstance(v, str) and v for v in
                       (vulnerability["id"], artifact["id"], artifact["name"], artifact["version"])):
                raise ValueError("Incomplete match")
        except (KeyError, TypeError) as exc:
            raise ValueError("Malformed scanner match") from exc
    return findings


def validate_evidence(sbom, scan, expected_image):
    """Validate collection independently of the scanner's process exit code."""
    try:
        expected_image = image_id(expected_image)
        pins = json.loads(LOCK.read_text())["tools"]
        for report, name in ((sbom, "syft"), (scan, "grype")):
            descriptor = report["descriptor"]
            if (descriptor["name"], descriptor["version"]) != (
                    name, pins[f"anchore/{name}"]["tag"].removeprefix("v")):
                raise ValueError("Unreviewed collection tool version")
            if report["source"]["type"] != "image":
                raise ValueError("Release evidence is not an image scan")
        if image_id(sbom["source"]["metadata"]["imageID"]) != expected_image or image_id(
                scan["source"]["target"]["imageID"]) != expected_image:
            raise ValueError("Evidence is for a different image")
        artifacts = sbom["artifacts"]
        if not isinstance(artifacts, list) or not artifacts:
            raise ValueError("Empty SBOM inventory")
        ids = {item["id"] for item in artifacts}
        if len(ids) != len(artifacts) or not all(ids):
            raise ValueError("Invalid SBOM package identifiers")
        names = {item["name"].lower().replace("_", "-") for item in artifacts if item["type"] == "python"}
        if not REQUIRED <= names:
            raise ValueError("SBOM is missing required application packages")
        config = scan["descriptor"]["configuration"]
        for field in ("only-fixed", "only-notfixed", "exclude", "ignore-wontfix"):
            if field not in config or config[field]:
                raise ValueError("Filtered scan cannot establish release readiness")
        if config.get("vex-documents") or config.get("ignore-states"):
            raise ValueError("Unreviewed vulnerability suppression")
        database = scan["descriptor"]["db"]["status"]
        built = datetime.fromisoformat(database["built"].replace("Z", "+00:00"))
        if built.tzinfo is None:
            raise ValueError("Database timestamp has no timezone")
        age = (datetime.now(timezone.utc) - built).total_seconds()
        if database["valid"] is not True or not -300 <= age <= 48 * 3600:
            raise ValueError("Invalid, stale or future-dated vulnerability database")
        findings = scan_findings(scan)
        if any(match["artifact"]["id"] not in ids for match in findings):
            raise ValueError("Scan findings are not bound to the collected SBOM")
        blocked = [{"package": m["artifact"]["name"], "version": m["artifact"]["version"],
                    "type": m["artifact"].get("type"), "id": m["vulnerability"]["id"],
                    "severity": m["vulnerability"]["severity"],
                    "fix_versions": m["vulnerability"].get("fix", {}).get("versions", [])}
                   for m in findings if m["vulnerability"]["severity"] in BLOCKING]
        return {"status": "blocked" if blocked else "passed", "image_id": expected_image,
                "packages_examined": len(artifacts), "matches_examined": len(findings),
                "suppressed_matches_examined": len(scan.get("ignoredMatches", [])),
                "severity_counts": dict(Counter(m["vulnerability"]["severity"] for m in findings)),
                "database_built": database["built"], "blocking_findings": blocked}
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("Incomplete release evidence") from exc


def digest(path):
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--container-report", type=Path, required=True)
    parser.add_argument("--tools", type=Path, required=True)
    parser.add_argument("--db-cache", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    # Ignore ambient scanner overrides and config discovery; evidence retains
    # actual effective configuration for inspection.
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GRYPE_", "SYFT_"))}
    env.update(GRYPE_DB_CACHE_DIR=str(args.db_cache.resolve()), GRYPE_DB_AUTO_UPDATE="false",
               GRYPE_CHECK_FOR_APP_UPDATE="false", SYFT_CHECK_FOR_APP_UPDATE="false")
    with tempfile.TemporaryDirectory(prefix="cra2-scan-") as directory:
        temp = Path(directory)
        config = temp / "scanner.json"
        config.write_text("{}\n")

        def run(tool, arguments, output, allowed=(0,)):
            with output.open("w") as stdout, output.with_suffix(".log").open("w") as stderr:
                result = subprocess.run([str(args.tools.resolve() / tool), "-c", str(config), *arguments],
                                        env=env, stdout=stdout, stderr=stderr, timeout=900)
            if result.returncode not in allowed:
                raise RuntimeError(f"{tool} collection failed; inspect {output.with_suffix('.log')}")
            return result.returncode

        run("grype", ["db", "update"], args.out / "database-update.txt")
        sbom_path, scan_path = args.out / "sbom.json", args.out / "scan.json"
        run("syft", ["oci-archive:" + str(args.archive.resolve()), "-o", "syft-json"], sbom_path)
        code = run("grype", ["sbom:" + str(sbom_path.resolve()), "-o", "json", "--fail-on", "high"],
                   scan_path, (0, 2))
        summary = validate_evidence(json.loads(sbom_path.read_text()), json.loads(scan_path.read_text()),
                                    json.loads(args.container_report.read_text())["image_id"])
        # Metadata only; no vulnerable Django code is downloaded or executed.
        canary = temp / "site-packages" / "Django-1.2.dist-info"
        canary.mkdir(parents=True)
        (canary / "METADATA").write_text("Metadata-Version: 2.1\nName: Django\nVersion: 1.2\n")
        canary_sbom, canary_scan = args.out / "canary-sbom.json", args.out / "canary-scan.json"
        run("syft", ["dir:" + str(canary.parent), "-o", "syft-json"], canary_sbom)
        canary_code = run("grype", ["sbom:" + str(canary_sbom.resolve()), "-o", "json", "--fail-on", "high"],
                          canary_scan, (0, 2))
        control = scan_findings(json.loads(canary_scan.read_text()))
        detected = sum(m["artifact"]["name"].lower() == "django" and
                       m["vulnerability"]["severity"] in {"High", "Critical"} for m in control)
        if canary_code != 2 or not detected:
            raise ValueError("Known-vulnerable metadata detection control failed")
        summary.update(scanner_exit_code=code, detection_control={"status": "passed", "blocking_matches": detected},
                       evidence_sha256={p.name: digest(p) for p in
                                        (args.archive, args.container_report, sbom_path, scan_path, canary_sbom, canary_scan)})
        (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps({k: v for k, v in summary.items() if k != "blocking_findings"}))
        raise SystemExit(0 if summary["status"] == "passed" else 2)


if __name__ == "__main__":
    main()
