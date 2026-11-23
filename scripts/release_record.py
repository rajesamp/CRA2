"""Prepare a source-pinned Podman context, verify release inputs and record scoped evidence."""
import argparse
from datetime import datetime, timezone
from hashlib import file_digest
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
from xml.etree import ElementTree

from evaluation.answer_packet import digest
from week2.release_info import COMPONENTS, ROOT, dataset_inputs, label_fields


class VerificationError(ValueError):
    """A fixed diagnostic safe to retain in the operator summary."""


def require(ok, message):
    if not ok:
        raise VerificationError(message)


def timestamp(value):
    require(isinstance(value, str) and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z", value), "invalid UTC timestamp")
    datetime.fromisoformat(value)
    return value


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def file_hash(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, mode="w", delete=False) as stream:
        stream.write(json.dumps(data, sort_keys=True, indent=2, allow_nan=False) + "\n")
    Path(stream.name).replace(path)


def identity(root, source, source_at):
    files = dataset_inputs(root)
    label = label_fields(source, digest(files))
    packets = root / "evals/answer-quality"
    evaluations = {name: digest(read(packets / filename)) for name, filename in (
        ("input_sha256", "development-v1.json"), ("rubric_sha256", "development-key-v1.json"),
        ("controls_sha256", "development-controls-v1.json"))}
    evaluations.update(packet_file_sha256=file_hash(packets / "development-v1.json"),
                       retrieval_sha256=file_hash(root / "evaluation/retrieval-cases-v1.json"),
                       lock_sha256=file_hash(root / "evaluation/uv.lock"), evaluator_revision=source)
    return {"schema_version": 1, **label, "source_at": timestamp(source_at), "components": COMPONENTS.copy(),
            "dataset_inputs": files, "evaluation": evaluations}


def verify_dataset(record, root):
    observed = dataset_inputs(root)
    require(record.get("dataset_inputs") == observed and record.get("dataset") == digest(observed),
            "dataset bytes or manifest mismatch")


def verify_identity(record, root, source):
    require(record.get("source") == source, "source revision mismatch")
    verify_dataset(record, root)
    expected = identity(root, source, record["source_at"])
    require(expected["evaluation"] == record.get("evaluation"), "evaluation packet, rubric or evaluator mismatch")
    require(expected == record, "release identity mismatch")


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def checkout(root, source):
    require(git(root, "rev-parse", "HEAD") == source, "source does not match checkout")
    require(not git(root, "status", "--porcelain", "--untracked-files=all"), "clean checkout required")
    return datetime.fromtimestamp(int(git(root, "show", "-s", "--format=%ct", source)), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def prepare(root, source, context, encoder):
    source_at = checkout(root, source)
    require(not context.resolve().is_relative_to(root.resolve()) and not context.exists(),
            "build context must be a new directory outside the checkout")
    # The clean build runs week1.setup_index on this archive before producing any label.
    require(encoder.is_file() and not encoder.is_symlink(), "regular encoder archive required")
    context.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=context.parent) as staging:
        stage = Path(staging) / "context"
        stage.mkdir()
        with tempfile.TemporaryFile() as archive:
            subprocess.run(["git", "-C", str(root), "archive", "--format=tar", source], stdout=archive, check=True)
            archive.seek(0)
            with tarfile.open(fileobj=archive, mode="r:") as tar:
                tar.extractall(stage, filter="data")
        record = identity(stage, source, source_at)
        dest = stage / "week1/.cache/models/fast-bge-small-en-v1.5.tar.gz"
        dest.parent.mkdir(parents=True)
        shutil.copyfile(encoder, dest)
        write(stage / "week2/_build_inputs.json", {**label_fields(source, record["dataset"]),
                                                  "dataset_inputs": record["dataset_inputs"]})
        stage.rename(context)
    return record


def sha(value):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{40}", value) is not None


def image_digest(value):
    return isinstance(value, str) and re.fullmatch(r"sha256:[a-f0-9]{64}", value) is not None


def bounded_hash(value):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def evidence_ref(ref):
    return bounded_hash(ref) or (isinstance(ref, str) and re.fullmatch(
        r"https://github\.com/rajesamp/CRA2/(?:actions/runs/[1-9]\d*|pull/[1-9]\d*)", ref))


def traffic(observation):
    require(set(observation) == {"at","components","evidence"} and evidence_ref(observation["evidence"]),
            "invalid traffic observation reference")
    timestamp(observation["at"])
    components = observation["components"]
    require(isinstance(components, dict) and set(components) == set(COMPONENTS), "component inventory incomplete")
    result = {}
    for component, rows in components.items():
        require(isinstance(rows, list) and 0 < len(rows) <= 100, "invalid traffic observation")
        active = []
        seen = set()
        for row in rows:
            require(set(row) == {"revision","percent","manifest"} and bounded_hash(row["revision"])
                    and row["revision"] not in seen, "invalid or duplicate revision fingerprint")
            seen.add(row["revision"])
            percent = row["percent"]
            require(type(percent) is int and 0 <= percent <= 100, "invalid traffic share")
            if percent:
                require(image_digest(row["manifest"]), "missing serving manifest digest")
                active.append(row.copy())
        require(sum(row["percent"] for row in active) == 100, "incomplete traffic shares")
        result[component] = active
    return {**observation, "components": result, "result": "observed"}


def hosted_result(row, source):
    require(set(row) == {"at","head","checkout","result","run","workflow","tests"}, "invalid hosted fields")
    timestamp(row["at"])
    require(all(sha(row[key]) for key in ("head","checkout")) and source in (row["head"], row["checkout"]),
            "hosted subject mismatch")
    require(type(row["run"]) is int and row["run"] > 0 and row["workflow"] == "week2-4"
            and row["result"] in {"passed","failed"} and type(row["tests"]) is int
            and row["tests"] >= (1 if row["result"] == "passed" else 0), "invalid hosted evidence")
    return {**row, "scope": "Week 2–4 tests and evaluation controls",
            "exact_checkout": row["checkout"] == source,
            "evidence": f"https://github.com/rajesamp/CRA2/actions/runs/{row['run']}"}


def assemble(record, *, hosted=None, serving=None, local=None, pr=None, acceptance=None):
    source = record["source"]
    result = {"schema_version": 1, "identity": record, "review": {"result": "unknown"},
              "local": {"result": "unknown"}, "hosted": {"result": "unknown"}, "build": {"result": "unknown"},
              "serving": {"result": "unknown"}, "acceptance": {"result": "pending"},
              "holds": {"invitations": "on_hold", "independent_labeling": "on_hold"}}
    if hosted is not None:
        result["hosted"] = hosted_result(hosted, source)
    if serving is not None:
        result["serving"] = traffic(serving)
    if pr is not None:
        require(set(pr) == {"head","number","result","at"} and pr["head"] == source
                and type(pr["number"]) is int and pr["number"] > 0
                and pr["result"] in {"draft","open","merged","closed"}, "PR subject or status mismatch")
        timestamp(pr["at"])
        result["review"] = {**pr, "evidence": f"https://github.com/rajesamp/CRA2/pull/{pr['number']}"}
    if local is not None:
        require(set(local) == {"source","at","tests","result","evidence"} and local["source"] == source
                and type(local["tests"]) is int and local["tests"] > 0 and local["result"] in {"passed","failed"}
                and bounded_hash(local["evidence"]), "local evidence mismatch")
        timestamp(local["at"])
        result["local"] = {**local, "scope": "Python 3.13 local tests"}
    if acceptance is not None:
        require(set(acceptance) == {"source","bundle","scope","at","evidence"} and acceptance["scope"] in
                {"protected-workspace","public-intro","both-components"} and bounded_hash(acceptance["evidence"]),
                "invalid owner decision")
        timestamp(acceptance["at"])
        if acceptance["source"] == source and acceptance["bundle"] == record["bundle"]:
            result["acceptance"] = {**acceptance, "result": "accepted"}
    return result


def junit_count(path):
    root = ElementTree.parse(path)
    suites = root.findall(".//testsuite") if root.getroot().tag != "testsuite" else [root.getroot()]
    cases = root.findall(".//testcase")
    require(bool(suites and cases) and sum(int(s.attrib["tests"]) for s in suites) == len(cases)
            and all(not any(c.find(key) is not None for key in ("error","skipped","failure")) for c in cases),
            "incomplete test evidence")
    return len(cases)


def verify_hosted_artifacts(checked, directory):
    reference = read(directory / "c3-public.json")
    for field in ("input_sha256", "rubric_sha256", "controls_sha256"):
        require(reference[field] == checked["evaluation"][field], "hosted evaluation binding mismatch")
    require(reference["public_status"] == "pass" and reference["matched_controls"] == reference["scheduled_controls"] > 0,
            "public controls did not pass")
    counts = {key: junit_count(directory / file) for key, file in (
        ("tests","tests.xml"), ("evaluation","evaluation-tests.xml"), ("answer_tests","c3-tests.xml"))}
    counts["public_controls"] = reference["matched_controls"]
    for name in ("canaries", "development-validation", "reserved", "faults"):
        data = read(directory / (name + ".json"))
        require(type(data["total"]) is int and data["passed"] == data["total"] > 0, f"{name} incomplete")
        if name in ("development-validation","reserved"):
            require(data["revision"] == checked["source"], f"{name} CI subject mismatch")
        if name != "canaries":
            require(data.get("provider_attempts") == 0, f"{name} provider attempts")
        counts[name] = data["passed"]
    scores = read(directory / "trulens.json")
    require(scores["passed"] is True and scores["source_commit"] == checked["source"]
            and scores["cases_sha256"] == checked["evaluation"]["retrieval_sha256"]
            and scores["environment_lock_sha256"] == checked["evaluation"]["lock_sha256"]
            and scores["provider_attempts"] == scores["network_attempts"] == 0, "retrieval evaluation binding mismatch")
    callbacks = read(directory / "c3-callbacks.json")
    require(callbacks["input_sha256"] == checked["evaluation"]["packet_file_sha256"] and callbacks["network_attempts"] == 0
            and len(callbacks["observations"]) > 0, "guarded callback binding mismatch")
    counts["guarded_callbacks"] = len(callbacks["observations"])
    counts["retrieval_cases"] = scores["case_count"]
    return counts


def failure(error, scope):
    reason = str(error) if isinstance(error, VerificationError) else "missing or invalid evidence"
    return {"result": "failed", "at": now(), "scope": scope, "reason": reason}


def operator_record(args):
    from scripts.release_publication import label_observation, verified_build
    invalid = (ValueError, OSError, KeyError, TypeError, AttributeError, IndexError, subprocess.SubprocessError)
    try:
        record = read(args.identity)
        require(record["source_at"] == checkout(ROOT, args.source), "source date mismatch")
        verify_identity(record, ROOT, args.source)
    except invalid as error:
        return {"schema_version": 1, "identity": failure(error, "release inputs")}
    result = assemble(record)
    try:
        obs = read(args.observations) if args.observations else {}
        fields = {"local":"local", "pr":"review", "acceptance":"acceptance", "serving":"serving", "hosted":"hosted"}
        require(isinstance(obs, dict) and set(obs) <= fields.keys() | {"browser"}, "unknown observation fields")
    except invalid as error:
        result["observations"] = failure(error, "operator observations")
        return result
    for name, axis in fields.items():
        if name in obs:
            try:
                result[axis] = assemble(record, **{name:obs[name]})[axis]
            except invalid as error:
                result[axis] = failure(error, axis)
    if args.publication:
        try:
            require(args.key is not None, "trusted public key required")
            result["build"] = verified_build(record, args.publication, args.key)
        except invalid as error:
            result["build"] = failure(error, "published image")
    try:
        result["browser"] = label_observation(record, result["build"], result["serving"], obs.get("browser"))
    except invalid as error:
        result["browser"] = failure(error, "browser label")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare","record","hosted"):
        sub = commands.add_parser(name)
        sub.add_argument("--source", required=True)
        sub.add_argument("--out", required=True, type=Path)
        if name == "prepare":
            sub.add_argument("--context", required=True, type=Path)
            sub.add_argument("--encoder", required=True, type=Path)
        if name == "record":
            sub.add_argument("--identity", required=True, type=Path)
            sub.add_argument("--observations", type=Path)
            sub.add_argument("--publication", type=Path)
            sub.add_argument("--key", type=Path)
        if name == "hosted":
            sub.add_argument("--head", required=True)
            sub.add_argument("--run", required=True, type=int)
            sub.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(ROOT, args.source, args.context, args.encoder)
    elif args.command == "hosted":
        source_at = checkout(ROOT, args.source)
        checked = identity(ROOT, args.source, source_at)
        require(read(args.evidence / "c3-callbacks.json")["app_tree"] == git(ROOT, "rev-parse", "HEAD:week2"),
                "guarded callback checkout mismatch")
        counts = verify_hosted_artifacts(checked, args.evidence)
        result = assemble(checked, hosted={"at": now(), "head": args.head, "checkout": args.source,
            "run": args.run, "result": "passed", "workflow": "week2-4", "tests": counts["tests"]})
        result["hosted"]["checks"] = counts

    else:
        result = operator_record(args)
    write(args.out, result)
    if any(isinstance(row, dict) and row.get("result") == "failed" for row in result.values()):
        parser.exit(2, "Release verification failed. See the recorded checks.\n")



if __name__ == "__main__":
    main()
