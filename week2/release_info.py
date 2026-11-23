"""Offline release label. The signed-in UI reads only this bounded metadata."""
from hashlib import sha256
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
LABEL_FILE = Path(__file__).with_name("_release.json")
FALLBACK = "Local build · Release unverified"
COMPONENTS = {"protected": "week2.cloud_app", "intro": "week2.landing"}


class VerificationError(ValueError):
    """A bounded binding diagnostic safe for the operator summary."""


def digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return sha256(encoded.encode()).hexdigest()


def label_fields(source, dataset):
    if not isinstance(source, str) or not re.fullmatch(r"[a-f0-9]{40}", source):
        raise ValueError("invalid source revision")
    if not isinstance(dataset, str) or not re.fullmatch(r"[a-f0-9]{64}", dataset):
        raise ValueError("invalid dataset digest")
    return {"bundle": "CRA2-" + digest([source, dataset])[:12], "source": source, "dataset": dataset}


def read_label(path=None):
    file = LABEL_FILE if path is None else path
    with file.open("rb") as stream:
        raw = stream.read(513)
    if len(raw) > 512:
        raise ValueError("invalid release label size")
    label = json.loads(raw)
    if not isinstance(label, dict) or label != label_fields(label.get("source"), label.get("dataset")):
        raise ValueError("invalid release label")
    return label


def render_label(label):
    return f"Release {label['bundle']} · Source {label['source'][:12]} · Dataset {label['dataset'][:12]}"


def release_label():
    try:
        return render_label(read_label())
    except (OSError, ValueError, RecursionError):
        return FALLBACK


def dataset_inputs(root):
    corpus = root / "week1/corpus"
    manifest = json.loads((corpus / "manifest.json").read_bytes())
    documents = sorted(corpus.glob("*.md"))
    if not isinstance(manifest, dict) or not documents or set(manifest) != {doc.stem for doc in documents}:
        raise ValueError("dataset manifest does not cover the corpus")
    paths = [root / "data" / name for name in ("checkout_system.json", "incidents.json", "sample_incidents.json")]
    paths += [corpus / "manifest.json", *documents]
    if any(path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) for path in paths):
        raise ValueError("dataset source outside the release")
    return {path.relative_to(root).as_posix(): sha256(path.read_bytes()).hexdigest() for path in paths}


def runtime_digest(root):
    """Fingerprint application files that the clean Podman context ships."""
    files = [root / name for name in ("pyproject.toml", "uv.lock", "README.md") if (root / name).is_file()]
    for name in ("cra2", "data", "evals", "week1", "week2", "week3", "week4"):
        for directory, children, names in os.walk(root / name):
            children[:] = [d for d in children if not d.startswith(".") and d not in {"tests","__pycache__"}]
            for filename in names:
                if filename.startswith(".") or filename.endswith((".sqlite3", ".sqlite3-wal", ".sqlite3-shm", ".pyc")):
                    continue
                path = Path(directory) / filename
                if path.relative_to(root).as_posix() not in {"week2/_build_inputs.json", "week2/_release.json"}:
                    files.append(path)
    entries = {}
    for path in files:
        if path.is_symlink():
            raise ValueError("unexpected linked runtime source")
        entries[path.relative_to(root).as_posix()] = sha256(path.read_bytes()).hexdigest()
    return digest(entries)


def check_index(root):
    from week1 import retrieval
    from week1.setup_index import provision_model

    provision_model(download=False)
    connection, meta = retrieval._open_index(root / "week1/.cache/index.sqlite3")
    connection.close()
    corpus = retrieval._corpus_digest(retrieval._documents(root / "week1/corpus"))
    encoder = retrieval._encoder_identity(retrieval._default_encoder())
    if corpus != meta["corpus_digest"] or encoder != meta["encoder_fingerprint"]:
        raise ValueError("retrieval index corpus or encoder mismatch")
    return {"corpus_digest": corpus, "encoder_fingerprint": encoder}


def package(root=ROOT):
    """The Podman build runs this after setting up its index, before copying the runtime."""
    manifest = root / "week2/_build_inputs.json"
    if not manifest.is_file():
        return
    expected = json.loads(manifest.read_bytes())
    files = dataset_inputs(root)
    label = label_fields(expected["source"], digest(files))
    if expected.get("runtime_sha256") != runtime_digest(root):
        raise ValueError("packaged runtime source does not match exported source")
    if expected != {**label, "dataset_inputs": files, "runtime_sha256": expected["runtime_sha256"]}:
        raise ValueError("packaged source or dataset binding mismatch")
    check_index(root)
    (root / "week2/_release.json").write_text(json.dumps(label) + "\n")
    manifest.unlink()


if __name__ == "__main__":
    package()
