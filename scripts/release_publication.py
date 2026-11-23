"""Verify a Podman scan, signed release evidence and a dated Cloud Run observation."""
import base64
from hashlib import sha256
import json

from scripts.release_record import VerificationError, bounded_hash, file_hash, image_digest, read, require, timestamp
from week2.release_info import label_fields, render_label


def verify_signature(key, payload, signature):
    """Verify the detached signature on the original bytes with the operator's trusted key."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
    verifier = serialization.load_pem_public_key(key.read_bytes())
    signed = base64.b64decode(signature.read_bytes().strip(), validate=True)
    try:
        if isinstance(verifier, ec.EllipticCurvePublicKey):
            verifier.verify(signed, payload, ec.ECDSA(hashes.SHA256()))
        elif isinstance(verifier, rsa.RSAPublicKey):
            require(verifier.key_size >= 2048, "unsupported release key")
            verifier.verify(signed, payload, padding.PKCS1v15(), hashes.SHA256())
        else:
            raise ValueError("unsupported release key")
    except InvalidSignature:
        raise VerificationError("invalid release signature") from None


def verified_build(identity, directory, key):
    """Read the exported registry evidence. Never contact the registry or use a signing key."""
    from scripts.scan_container import validate_evidence
    info = read(directory / "publication.json")
    require(set(info) == {"at","manifest"} and image_digest(info["manifest"]), "invalid registry observation")
    timestamp(info["at"])
    manifest = info["manifest"]
    require("sha256:" + file_hash(directory / "manifest.json") == manifest, "registry manifest digest mismatch")
    image = read(directory / "manifest.json")
    require(image.get("schemaVersion") == 2 and isinstance(image.get("layers"), list)
            and image["layers"] and "config" in image, "a resolved single-platform image manifest is required")
    config = image["config"]["digest"]
    require(image_digest(config) and "sha256:" + file_hash(directory / "config.json") == config,
            "registry config digest mismatch")
    platform = read(directory / "config.json")
    container = read(directory / "container.json")
    label = label_fields(identity["source"], identity["dataset"])
    require((platform.get("os"), platform.get("architecture")) == ("linux","amd64")
            and (container.get("os"), container.get("architecture")) == ("linux","amd64")
            and container.get("image_id","").removeprefix("sha256:") == config[7:]
            and container.get("release_label") == label, "tested config, platform or label mismatch")
    scan = read(directory / "summary.json")
    measured = validate_evidence(read(directory / "sbom.json"), read(directory / "scan.json"), config)
    require(measured["status"] == "passed" and all(scan.get(k) == v for k,v in measured.items())
            and scan["scanner_exit_code"] == 0 and scan["detection_control"]["status"] == "passed"
            and scan["detection_control"]["blocking_matches"] > 0, "scan or detection control failed")
    for filename in ("container.json","sbom.json","scan.json","canary-scan.json"):
        require(scan["evidence_sha256"].get(filename) == file_hash(directory / filename), "scan evidence binding mismatch")
    from scripts.scan_container import scan_findings
    detected = [m for m in scan_findings(read(directory / "canary-scan.json")) if m["artifact"]["name"].lower() == "django"
                and m["vulnerability"]["severity"] in {"Critical","High"}]
    require(len(detected) == scan["detection_control"]["blocking_matches"], "detection count mismatch")
    claim_bytes = (directory / "image-signature.json").read_bytes()
    statement_bytes = (directory / "provenance.json").read_bytes()
    verify_signature(key, claim_bytes, directory / "image.sig")
    verify_signature(key, statement_bytes, directory / "provenance.sig")
    claim = json.loads(claim_bytes)["critical"]
    require(claim["type"] == "cosign container image signature" and claim["image"]["docker-manifest-digest"] == manifest,
            "signed image subject mismatch")
    statement = json.loads(statement_bytes)
    require(statement.get("_type") == "https://in-toto.io/Statement/v1"
            and statement.get("predicateType") == "https://slsa.dev/provenance/v1"
            and len(statement["subject"]) == 1 and statement["subject"][0]["digest"]["sha256"] == manifest[7:],
            "signed provenance subject mismatch")
    materials = statement["predicate"]["buildDefinition"]["resolvedDependencies"]
    repo = "git+https://github.com/rajesamp/CRA2"
    sources = [dep["digest"].get("gitCommit") for dep in materials if dep.get("uri") == repo]
    require(sources == [identity["source"]], "signed source mismatch")
    return {"result":"verified", "scope":"linux/amd64 image, scan, signature and provenance",
            "at":info["at"], "manifest":manifest, "config":config, "source":identity["source"],
            "bundle":identity["bundle"], "scan_sha256":file_hash(directory / "summary.json"),
            "key_sha256":file_hash(key), "provenance_sha256":sha256(statement_bytes).hexdigest()}


def label_observation(identity, build, serving, browser):
    if browser is None:
        return {"result":"unknown"}
    keys = {"at","revision","label","evidence","owner_allowed","anonymous_denied","unlisted_denied","traffic_evidence"}
    require(set(browser) == keys and bounded_hash(browser["evidence"]) and bounded_hash(browser["traffic_evidence"]) and
            (browser["revision"] is None or bounded_hash(browser["revision"])), "invalid browser observation")
    timestamp(browser["at"])
    row = {"at":browser["at"], "scope":"signed-in protected workspace", "evidence":browser["evidence"],
           "revision":browser["revision"]}
    if serving["result"] != "observed" or build["result"] != "verified" or browser["revision"] is None:
        return {**row, "result":"unknown"}
    active = {r["revision"]:r["manifest"] for r in serving["components"]["protected"]}
    require(all(type(browser[k]) is bool for k in ("owner_allowed","anonymous_denied","unlisted_denied")),
            "invalid access observation")
    # Link the browser to its traffic capture even when the HTTP requests finish at different times.
    if browser["traffic_evidence"] != serving["evidence"]:
        return {**row, "result":"unknown"}
    ok = (active.get(browser["revision"]) == build["manifest"]
          and browser["label"] == render_label(label_fields(identity["source"], identity["dataset"]))
          and all(browser[k] for k in ("owner_allowed","anonymous_denied","unlisted_denied")))
    return {**row, "result":"passed" if ok else "failed"}
