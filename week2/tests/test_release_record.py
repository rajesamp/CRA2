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


def test_eval_packet_and_component_bindings():
    from scripts import release_record as release
    for key in ("input_sha256","rubric_sha256","controls_sha256","retrieval_sha256","lock_sha256","evaluator_revision"):
        candidate = release.identity(ROOT, SOURCE, AT)
        candidate["evaluation"][key] = "0" * 64
        with pytest.raises(ValueError, match="evaluation"):
            release.verify_identity(candidate, ROOT, SOURCE)
    candidate = release.identity(ROOT, SOURCE, AT)
    candidate["components"]["protected"] = "unknown"
    with pytest.raises(ValueError, match="identity"):
        release.verify_identity(candidate, ROOT, SOURCE)


@pytest.mark.parametrize("filename", ["data/incidents.json","data/sample_incidents.json","week1/corpus/manifest.json","document"])
def test_data_identity_covers_every_source_family(tmp_path, filename):
    from scripts import release_record as release
    record = release.identity(ROOT, SOURCE, AT)
    for name in record["dataset_inputs"]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, path)
    if filename == "document":
        filename = next(n for n in record["dataset_inputs"] if n.endswith(".md"))
    with (tmp_path / filename).open("ab") as output:
        output.write(b"\n")
    with pytest.raises(ValueError, match="dataset"):
        release.verify_dataset(record, tmp_path)


def test_traffic_shares_and_revision_bound_browser():
    from scripts import release_record as release
    from scripts.release_publication import label_observation
    from week2.release_info import render_label
    record = release.identity(ROOT, SOURCE, AT)
    manifest = "sha256:" + "1" * 64
    other = "sha256:" + "2" * 64
    revisions = [dict(revision=c * 64, percent=p, manifest=m) for c,p,m in
                 (("a",70,manifest),("b",30,other),("c",0,other))]
    evidence = "4" * 64
    obs = dict(at=AT, evidence=evidence, components={"protected": revisions, "intro": [dict(revisions[0], percent=100)]})
    serving = release.traffic(obs)
    assert [r["percent"] for r in serving["components"]["protected"]] == [70,30]
    assert serving["at"] == AT
    build = {"result":"verified","manifest":manifest}
    owner = dict(at=AT, revision="a"*64, evidence="5"*64, traffic_evidence=evidence, label=render_label(record),
                 owner_allowed=True, anonymous_denied=True, unlisted_denied=True)
    def result(**changes):
        return label_observation(record, build, serving, dict(owner, **changes))["result"]
    assert result() == "passed"
    assert result(revision=None) == result(traffic_evidence="f"*64) == "unknown"
    for change in ({"revision":"b"*64},{"revision":"c"*64},{"label":"another bundle"},{"unlisted_denied":False}):
        assert result(**change) == "failed"
    revisions[0]["percent"] = 50
    with pytest.raises(ValueError, match="share"):
        release.traffic(obs)


def test_prior_acceptance_does_not_transfer_and_hosted_run_must_identify_candidate():
    from scripts import release_record as release
    record = release.identity(ROOT, SOURCE, AT)
    signed = dict(source=SOURCE, bundle=record["bundle"], scope="protected-workspace", at=AT, evidence="5"*64)
    assert release.assemble(record, acceptance=signed)["acceptance"]["result"] == "accepted"
    assert release.assemble(record, acceptance=dict(signed, source="b"*40))["acceptance"] == {"result":"pending"}
    with pytest.raises(ValueError, match="hosted subject"):
        release.assemble(record, hosted=dict(at=AT, head="b"*40, checkout="c"*40,
                         result="passed", run=123, workflow="week2-4", tests=54))


def test_ui_label_is_bounded_offline_and_anonymous_intro_has_no_private_values(tmp_path, monkeypatch):
    import json
    import socket
    from fastapi.testclient import TestClient
    from week2 import release_info as labels
    from week2.landing import create_app
    path = tmp_path / "release.json"
    monkeypatch.setattr(labels, "LABEL_FILE", path)
    def deny_network(*args, **kwargs):
        pytest.fail("loading a label attempted network access")
    monkeypatch.setattr(socket.socket, "connect", deny_network)
    monkeypatch.setattr(socket, "getaddrinfo", deny_network)
    label = labels.label_fields(SOURCE, "e"*64)
    assert labels.release_label() == labels.FALLBACK
    path.write_text(json.dumps(label))
    assert labels.release_label() == labels.render_label(label)
    for raw in (b"{}",b"invalid",b"["*511,json.dumps({**label,"private":"secret-fixture-marker"}).encode(),b"x"*600):
        path.write_bytes(raw)
        assert labels.release_label() == labels.FALLBACK
    client = TestClient(create_app("https://protected-synthetic.a.run.app/"))
    for route in ("/","/styles.css","/healthz","/signin"):
        res = client.get(route, follow_redirects=False)
        for marker in ("secret-fixture-marker",label["bundle"]):
            assert marker not in str(res.headers) + res.text


def test_detached_build_requires_matching_signed_manifest_config_source_and_scan(tmp_path):
    import base64
    import json
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from scripts import release_record as release
    from scripts.release_publication import verified_build
    from scripts.scan_container import validate_evidence
    from week2.tests.test_release_evidence import reports
    from week2.release_info import label_fields
    rec = release.identity(ROOT, SOURCE, AT)
    save = lambda name, value: release.write(tmp_path / name, value)
    key = ec.generate_private_key(ec.SECP256R1())
    pem = tmp_path / "operator.pem"
    pem.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    save("config.json", {"os":"linux","architecture":"amd64"})
    config = "sha256:" + release.file_hash(tmp_path / "config.json")
    save("manifest.json", {"schemaVersion":2, "layers":[{}], "config":{"digest":config}})
    manifest = "sha256:" + release.file_hash(tmp_path / "manifest.json")
    save("publication.json", {"at":AT,"manifest":manifest})
    sbom, scan = reports()
    sbom["source"]["metadata"]["imageID"] = scan["source"]["target"]["imageID"] = config
    save("sbom.json",sbom)
    save("scan.json",scan)
    save("container.json", {"release_label":label_fields(SOURCE,rec["dataset"]), "image_id":config,"os":"linux","architecture":"amd64"})
    save("canary-scan.json", {"matches":[{"artifact":{"id":"1","name":"django","version":"1.2"},
                                          "vulnerability":{"id":"fixture","severity":"High"}}]})
    summary = validate_evidence(sbom, scan, config)
    summary.update(scanner_exit_code=0, detection_control={"status":"passed","blocking_matches":1},
                   evidence_sha256={n:release.file_hash(tmp_path/n) for n in ("sbom.json","scan.json","container.json","canary-scan.json")})
    save("summary.json", summary)
    def sign(name, sig, obj):
        save(name, obj)
        signature = key.sign((tmp_path/name).read_bytes(), ec.ECDSA(hashes.SHA256()))
        (tmp_path/sig).write_bytes(base64.b64encode(signature))
    claim = {"critical":{"type":"cosign container image signature","image":{"docker-manifest-digest":manifest}}}
    sign("image-signature.json","image.sig",claim)
    provenance = {"_type":"https://in-toto.io/Statement/v1","predicateType":"https://slsa.dev/provenance/v1",
                  "subject":[{"digest":{"sha256":manifest[7:]}}], "predicate":{"buildDefinition":
                  {"resolvedDependencies":[{"uri":"git+https://github.com/rajesamp/CRA2","digest":{"gitCommit":SOURCE}}]}}}
    sign("provenance.json","provenance.sig",provenance)
    assert verified_build(rec, tmp_path, pem)["manifest"] == manifest
    for name, change, reason in (
        ("publication.json",lambda d:d.update(manifest=config),"manifest"),
        ("config.json",lambda d:d.update(architecture="arm64"),"config"),
        ("container.json",lambda d:d.update(image_id=manifest),"config"),
        ("summary.json",lambda d:d.update(scanner_exit_code=2),"scan"),
        ("image-signature.json",lambda d:d.update(extra="changed"),"signature")):
        p = tmp_path / name
        before = p.read_bytes()
        data = json.loads(before)
        change(data)
        save(name,data)
        with pytest.raises(ValueError, match=reason):
            verified_build(rec,tmp_path,pem)
        p.write_bytes(before)
    provenance["predicate"]["buildDefinition"]["resolvedDependencies"][0]["digest"]["gitCommit"] = "e"*40
    sign("provenance.json","provenance.sig",provenance)
    with pytest.raises(ValueError, match="source"):
        verified_build(rec,tmp_path,pem)


def test_packaging_rejects_stale_input_and_writes_only_public_fields(tmp_path, monkeypatch):
    from week2 import release_info as labels
    from scripts import release_record as record
    candidate = record.identity(ROOT, SOURCE, AT)
    for filename in candidate["dataset_inputs"]:
        target = tmp_path / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / filename, target)
    expected = labels.label_fields(SOURCE, candidate["dataset"])
    receipt = tmp_path / "week2/_build_inputs.json"
    record.write(receipt, {**expected,"dataset_inputs":{}, "runtime_sha256":labels.runtime_digest(tmp_path)})
    with pytest.raises(ValueError, match="dataset binding"):
        labels.package(tmp_path)
    calls = []
    monkeypatch.setattr(labels, "check_index", calls.append)
    record.write(receipt, {**expected, "dataset_inputs":candidate["dataset_inputs"], "runtime_sha256":labels.runtime_digest(tmp_path)})
    labels.package(tmp_path)
    assert calls == [tmp_path]
    assert not receipt.exists()
    assert labels.read_label(tmp_path / "week2/_release.json") == expected


def test_failed_publication_keeps_independent_traffic_observation(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from scripts import release_record as record
    identity = record.identity(ROOT, SOURCE, AT)
    record.write(tmp_path/"identity.json", identity)
    live = [dict(revision="a"*64, percent=100, manifest="sha256:"+"c"*64)]
    record.write(tmp_path/"observation.json", {"serving":{"at":AT, "evidence":"1"*64,
                  "components":{"protected":live,"intro":live}}})
    monkeypatch.setattr(record, "checkout", lambda *_: AT)
    args = SimpleNamespace(source=SOURCE, identity=tmp_path/"identity.json", observations=tmp_path/"observation.json",
                           publication=tmp_path/"missing", key=tmp_path/"missing-key")
    result = record.operator_record(args)
    assert result["build"]["result"] == "failed" and result["serving"]["result"] == "observed"
    assert result["browser"]["result"] == "unknown" and result["acceptance"]["result"] == "pending"


def test_build_rejects_source_drift_after_export(tmp_path, monkeypatch):
    from scripts import release_record as records
    from week2 import release_info as labels
    # A valid dataset can accompany the wrong application bytes.
    for filename in labels.dataset_inputs(ROOT):
        target = tmp_path / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / filename, target)
    app = tmp_path / "week2/app.py"
    app.parent.mkdir()
    app.write_text("version = 1\n")
    fields = labels.label_fields(SOURCE, labels.digest(labels.dataset_inputs(tmp_path)))
    build = {**fields, "dataset_inputs": labels.dataset_inputs(tmp_path),
             "runtime_sha256": labels.runtime_digest(tmp_path)}
    records.write(tmp_path / "week2/_build_inputs.json", build)
    app.write_text("version = 2\n")
    monkeypatch.setattr(labels, "check_index", lambda *_: pytest.fail("expected application source check first"))
    with pytest.raises(ValueError, match="runtime source"):
        labels.package(tmp_path)
