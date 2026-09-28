"""Explicit, checksum-pinned model provisioning and local index construction.

Run ``python -m week1.setup_index --download-model`` for the one-time public
model download. Without that flag this command only uses verified local files.
No Groq API key or cloud embedding service is used by model provisioning.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from urllib.request import urlopen

from cra2.secrets import reject_credentials
from week1 import retrieval

MODEL_FOLDER = "fast-bge-small-en-v1.5"
MODEL_URL = (
    "https://storage.googleapis.com/qdrant-fastembed/fast-bge-small-en-v1.5.tar.gz"
)
ARCHIVE_SHA256 = "3858004b3822f64f940280874b8f2d2dc25b34a4f3eb3cdf617bdceeb21ed9ed"
ARCHIVE_BYTES = 76_692_531
# Hashes from the pinned official Qdrant archive. Check existing local files too;
# an unrelated directory is never overwritten or accepted as this model.
ARTIFACT_SHA256 = {
    "config.json": "cf423cc7d3c3202d0fecc4ca622fd996678c0b5a8abd56ba014413b8b4265639",
    "model_optimized.onnx": "20e3bd678b8e67a722f151f3ee1e3827fc3f230839c0d57c025a3753cefa6b2e",
    "ort_config.json": "97e78d1d21c2eb719e865b018f17915df6a12ed987446eb7f3f3a783a5afb1e1",
    "special_tokens_map.json": "b6d346be366a7d1d48332dbc9fdf3bf8960b5d879522b7799ddba59e76237ee3",
    "tokenizer.json": "d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66",
    "tokenizer_config.json": "e1790949631401af1bfb6c9c7aeec7fcf612e274d73579d99f704faea40c8ba7",
    "vocab.txt": "07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3",
}
TOKENIZER_INSTALLED_SHA256 = (
    "9261e7d79b44c8195c1cada2b453e55b00aeb81e907a6664974b4d7776172ab3"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _validate_model(directory: Path, *, original: bool = False) -> None:
    if directory.is_symlink() or not directory.is_dir():
        raise retrieval.RetrievalError("Model cache is not a regular directory")
    if {path.name for path in directory.iterdir()} != set(ARTIFACT_SHA256):
        raise retrieval.RetrievalError(
            "Model cache has unexpected or missing files; it was left unchanged"
        )
    for name, expected in ARTIFACT_SHA256.items():
        if name == "tokenizer_config.json" and not original:
            expected = TOKENIZER_INSTALLED_SHA256
        path = directory / name
        if path.is_symlink() or not path.is_file() or _sha256(path) != expected:
            raise retrieval.RetrievalError(
                "Model artifact checksum failed; the cache was left unchanged"
            )


def _prepare_model(directory: Path) -> None:
    tokenizer = directory / "tokenizer_config.json"
    if (
        not directory.is_symlink()
        and tokenizer.is_file()
        and not tokenizer.is_symlink()
        and _sha256(tokenizer) == ARTIFACT_SHA256.get("tokenizer_config.json")
    ):
        _validate_model(directory, original=True)
        # The official archive predates FastEmbed's strict context check: its
        # tokenizer uses the HF "unknown maximum" sentinel. The verified model
        # config and BGE-small-en-v1.5 descriptor both specify 512 positions.
        # Normalize only that limit; retain and verify original archive hashes.
        settings = json.loads(tokenizer.read_text(encoding="utf-8"))
        settings["model_max_length"] = 512
        encoded = (json.dumps(settings, sort_keys=True, indent=2) + "\n").encode(
            "utf-8"
        )
        if hashlib.sha256(encoded).hexdigest() != TOKENIZER_INSTALLED_SHA256:
            raise retrieval.RetrievalError(
                "Unexpected tokenizer configuration; model cache was left unchanged"
            )
        descriptor, name = tempfile.mkstemp(prefix=".tokenizer-", dir=directory)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(encoded)
            os.replace(temporary, tokenizer)
        finally:
            temporary.unlink(missing_ok=True)
    _validate_model(directory)


def _verify_archive(path: Path) -> None:
    if (
        path.is_symlink()
        or not path.is_file()
        or path.stat().st_size != ARCHIVE_BYTES
        or _sha256(path) != ARCHIVE_SHA256
    ):
        raise retrieval.RetrievalError(
            "Model archive checksum or size failed; no model was installed"
        )


def _extract_archive(archive: Path, cache: Path) -> Path:
    """Write only known regular files into a fresh temporary directory."""
    target = cache / MODEL_FOLDER
    if target.exists() or target.is_symlink():
        _prepare_model(target)
        return target
    _verify_archive(archive)
    with tempfile.TemporaryDirectory(prefix=".cra2-model-", dir=cache) as temporary:
        staging = Path(temporary)
        directory = staging / MODEL_FOLDER
        directory.mkdir()
        with tarfile.open(archive, "r:gz") as bundle:
            members = bundle.getmembers()
            seen = set()
            total_size = 0
            for member in members:
                name = PurePosixPath(member.name)
                if member.name == MODEL_FOLDER and member.isdir():
                    continue
                if (
                    name.is_absolute()
                    or len(name.parts) != 2
                    or name.parts[0] != MODEL_FOLDER
                    or name.name not in ARTIFACT_SHA256
                    or not member.isfile()
                    or member.name in seen
                    or member.size < 0
                ):
                    raise retrieval.RetrievalError(
                        "Model archive contains an unsafe or unexpected entry"
                    )
                seen.add(member.name)
                total_size += member.size
                if total_size > 200_000_000:
                    raise retrieval.RetrievalError(
                        "Model archive expands beyond the supported size"
                    )
            if seen != {f"{MODEL_FOLDER}/{name}" for name in ARTIFACT_SHA256}:
                raise retrieval.RetrievalError("Model archive is incomplete")
            for member in members:
                if member.isfile():
                    source = bundle.extractfile(member)
                    if source is None:
                        raise retrieval.RetrievalError(
                            "Model archive contains an unreadable file"
                        )
                    with (
                        source,
                        (directory / PurePosixPath(member.name).name).open(
                            "xb"
                        ) as output,
                    ):
                        shutil.copyfileobj(source, output)
        _prepare_model(directory)
        if target.exists() or target.is_symlink():
            raise retrieval.RetrievalError(
                "Model cache appeared during setup; retry to verify it"
            )
        directory.rename(target)
    return target


def provision_model(*, download: bool = False) -> Path:
    cache = retrieval.MODEL_CACHE
    reject_credentials(str(cache))
    target = cache / MODEL_FOLDER
    if target.exists() or target.is_symlink():
        _prepare_model(target)
        return target
    archive = cache / f"{MODEL_FOLDER}.tar.gz"
    if not archive.exists():
        if not download:
            raise retrieval.RetrievalError(
                "Model is missing; use --download-model for the explicit public download"
            )
        cache.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(
            prefix=".cra2-download-", suffix=".tar.gz", dir=cache
        )
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as output:
                try:
                    with urlopen(MODEL_URL, timeout=30) as response:
                        if response.geturl() != MODEL_URL:
                            raise retrieval.RetrievalError(
                                "Unexpected model download redirect"
                            )
                        downloaded = 0
                        while block := response.read(1024 * 1024):
                            downloaded += len(block)
                            if downloaded > ARCHIVE_BYTES:
                                raise retrieval.RetrievalError(
                                    "Model download exceeds its pinned size"
                                )
                            output.write(block)
                except Exception:
                    raise retrieval.RetrievalError(
                        "Public model download failed; no model was installed"
                    ) from None
            _verify_archive(temporary)
            # Publish without replacing a file created while downloading.
            os.link(temporary, archive)
        finally:
            temporary.unlink(missing_ok=True)
    return _extract_archive(archive, cache)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--download-model",
        action="store_true",
        help="Allow the public checksum-pinned Qdrant model download",
    )
    parser.add_argument("--corpus", type=Path, default=Path(__file__).parent / "corpus")
    parser.add_argument(
        "--index", type=Path, default=Path(__file__).parent / ".cache" / "index.sqlite3"
    )
    args = parser.parse_args(argv)
    reject_credentials([str(args.corpus), str(args.index)])
    try:
        provision_model(download=args.download_model)
        counts = retrieval.build_index(args.corpus, args.index)
    except Exception:
        # CLI errors are deliberately generic; raw paths/provider messages and
        # traceback locals do not belong in a shareable setup transcript.
        print(
            "Setup failed. Check local corpus/model files; use --download-model only when provisioning is intended."
        )
        return 1
    print(json.dumps(counts, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
