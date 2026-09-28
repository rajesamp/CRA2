"""Local incident/document retrieval with a versioned SQLite vector index.

FastEmbed and model weights are loaded only when an encoder is needed. Model
provisioning is explicit: runtime retrieval never downloads missing weights.
Source documents stay authoritative; changed content requires an index rebuild.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
from functools import lru_cache
from importlib.metadata import version
from itertools import islice
from pathlib import Path

from cra2 import config
from cra2.incidents import load_incidents
from cra2.secrets import reject_credentials

MODEL_NAME = "BAAI/bge-small-en-v1.5"
DIMENSIONS = 384
SCHEMA_VERSION = "1"
CHUNK_WORDS, CHUNK_OVERLAP = 160, 30
REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_CACHE = Path(__file__).resolve().parent / ".cache" / "models"
LOCAL_MODEL_DIR = MODEL_CACHE / "fast-bge-small-en-v1.5"
_COLUMNS = (
    "chunk_id",
    "doc_id",
    "title",
    "source",
    "kind",
    "service",
    "source_dataset",
    "text",
    "embedding",
)
_META_KEYS = {
    "schema_version",
    "model",
    "dimensions",
    "chunk_words",
    "chunk_overlap",
    "corpus_dir",
    "corpus_digest",
    "documents",
    "chunks",
    "encoder_fingerprint",
}


class RetrievalError(ValueError):
    """Invalid corpus, unavailable model, or unusable local index."""


class StaleIndexError(RetrievalError):
    """The index no longer describes the current model/chunking/source corpus."""


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RetrievalError("Corpus manifest contains duplicate keys")
        result[key] = value
    return result


def _source(path: Path, corpus_dir: Path | None = None) -> str:
    """Repository-relative paths, or corpus-relative labels for an external corpus."""
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return ("corpus/" if corpus_dir is not None else "data/") + path.name


def _documents(corpus_dir: Path) -> list[dict]:
    corpus_dir = Path(corpus_dir).resolve()
    reject_credentials(str(corpus_dir))
    if not corpus_dir.is_dir():
        raise RetrievalError("Corpus directory is missing")
    manifest_path = corpus_dir / "manifest.json"
    if manifest_path.is_symlink():
        raise RetrievalError("Corpus manifest must not be a symbolic link")
    try:
        with manifest_path.open(encoding="utf-8") as stream:
            raw = stream.read(100_001)
        if len(raw) > 100_000:
            raise RetrievalError("Corpus manifest is too large")
        manifest = json.loads(raw, object_pairs_hook=_json_object)
    except (OSError, UnicodeError, ValueError, RecursionError):
        raise RetrievalError("Corpus manifest must be valid bounded JSON") from None
    reject_credentials(manifest)
    paths = sorted(corpus_dir.glob("*.md"))
    if not isinstance(manifest, dict) or not paths or len(paths) > 2000:
        raise RetrievalError(
            "Corpus must contain a manifest and between 1 and 2,000 Markdown documents"
        )
    if set(manifest) != {path.stem for path in paths}:
        raise RetrievalError(
            "Manifest entries must exactly cover the Markdown documents"
        )
    incidents = load_incidents(config.DATA_DIR)
    reject_credentials(incidents)
    services = {incident["service"] for incident in incidents}
    documents = []
    for incident in incidents:
        dataset = incident["source_dataset"]
        filename = (
            "incidents.json" if dataset == "synthetic" else "sample_incidents.json"
        )
        text = "\n".join(
            [
                f"# Incident {incident['incident_id']}",
                f"Service: {incident['service']}",
                f"Date: {incident['date']}",
                f"Change type: {incident['change_type']}",
                f"Severity: {incident['severity']}",
                f"Source dataset: {dataset}",
                f"Source label: {incident.get('source', 'synthetic')}",
                f"Root cause: {incident['root_cause']}",
            ]
        )
        documents.append(
            {
                "doc_id": incident["incident_id"],
                "title": f"Incident {incident['incident_id']}",
                "source": _source(config.DATA_DIR / filename)
                + "#"
                + incident["incident_id"],
                "kind": "incident",
                "service": incident["service"],
                "source_dataset": dataset,
                "text": text,
            }
        )
    for path in paths:
        info = manifest[path.stem]
        if (
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", path.stem)
            or path.is_symlink()
            or path.resolve().parent != corpus_dir
        ):
            raise RetrievalError(
                "Corpus files must have safe names and stay inside the corpus directory"
            )
        if (
            not isinstance(info, dict)
            or set(info) != {"kind", "service"}
            or not isinstance(info["kind"], str)
            or info["kind"] not in {"postmortem", "runbook", "policy"}
            or (
                info["service"] is not None
                and (
                    not isinstance(info["service"], str)
                    or info["service"] not in services
                )
            )
        ):
            raise RetrievalError(
                "Manifest entries require a known kind and an explicit incident service or null"
            )
        if info["kind"] == "postmortem" and info["service"] is None:
            raise RetrievalError("Postmortems require an explicit service")
        try:
            with path.open(encoding="utf-8") as stream:
                text = stream.read(100_001)
        except (OSError, UnicodeError):
            raise RetrievalError(
                "Corpus documents must be readable UTF-8 text"
            ) from None
        reject_credentials(text)
        if not text.strip() or len(text) > 100_000:
            raise RetrievalError(
                "Corpus documents must be nonempty and at most 100,000 characters"
            )
        title = next(
            (line[2:].strip() for line in text.splitlines() if line.startswith("# ")),
            "",
        )
        if not title or len(title) > 300:
            raise RetrievalError(
                "Every corpus document needs a bounded level-one title"
            )
        documents.append(
            {
                "doc_id": path.stem,
                "title": title,
                "source": _source(path, corpus_dir),
                "kind": info["kind"],
                "service": info["service"],
                "source_dataset": "corpus_markdown",
                "text": text,
            }
        )
    if len({document["doc_id"] for document in documents}) != len(documents):
        raise RetrievalError("Incident and Markdown document IDs must be unique")
    documents.sort(key=lambda document: document["doc_id"])
    reject_credentials(documents)
    return documents


def _corpus_digest(documents: list[dict]) -> str:
    encoded = json.dumps(
        documents, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _chunks(documents: list[dict]) -> list[dict]:
    chunks = []
    for document in documents:
        words = document["text"].split()
        start, number = 0, 1
        while start < len(words):
            end = min(start + CHUNK_WORDS, len(words))
            chunks.append(
                {
                    **document,
                    "chunk_id": f"{document['doc_id']}#chunk-{number:03d}",
                    "text": " ".join(words[start:end]),
                }
            )
            if end == len(words):
                break
            start, number = end - CHUNK_OVERLAP, number + 1
    if len(chunks) > 20_000:
        raise RetrievalError("Corpus exceeds the 20,000 chunk limit")
    return chunks


@lru_cache(maxsize=1)
def _default_encoder():
    from fastembed import TextEmbedding

    # Provisioning downloads belong to an explicit setup step, not a user query.
    options = (
        {"specific_model_path": str(LOCAL_MODEL_DIR)}
        if LOCAL_MODEL_DIR.is_dir()
        else {}
    )
    try:
        encoder = TextEmbedding(
            model_name=MODEL_NAME,
            cache_dir=str(MODEL_CACHE),
            local_files_only=True,
            threads=2,
            **options,
        )
    except Exception:
        raise RetrievalError(
            "Local model is unavailable; run python -m week1.setup_index --download-model"
        ) from None
    # FastEmbed is pinned by week1/uv.lock. Fingerprint the actual artifacts it
    # loaded, including tokenization, instead of guessing a model revision.
    directory = Path(encoder.model._model_dir)
    artifacts = [directory / encoder.model.model_description.model_file]
    artifacts.extend(
        directory / filename
        for filename in (
            "config.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "vocab.txt",
        )
        if (directory / filename).is_file()
    )
    digest = hashlib.sha256(version("fastembed").encode("utf-8"))
    for artifact in sorted(artifacts):
        digest.update(artifact.relative_to(directory).as_posix().encode("utf-8"))
        with artifact.open("rb") as stream:
            while block := stream.read(1024 * 1024):
                digest.update(block)
    encoder._cra2_fingerprint = "fastembed-artifacts-sha256:" + digest.hexdigest()
    return encoder


def _encoder_identity(encoder) -> str:
    if hasattr(encoder, "_cra2_fingerprint"):
        return encoder._cra2_fingerprint
    # Encoder injection is a test/embedding-adapter interface, not measured BGE
    # evidence. Adapters can supply a versioned fingerprint for stricter checks.
    return "injected:" + str(
        getattr(
            encoder,
            "fingerprint",
            type(encoder).__module__ + "." + type(encoder).__qualname__,
        )
    )


def _vector(value):
    import numpy as np

    failure = None
    try:
        vector = np.asarray(value, dtype=np.float32)
        if vector.shape != (DIMENSIONS,) or not np.isfinite(vector).all():
            raise ValueError("Invalid dimensions or nonfinite vector")
        norm = float(np.linalg.norm(vector.astype(np.float64)))
        if not norm > 0:
            raise ValueError("Zero vector")
        vector = (vector.astype(np.float64) / norm).astype("<f4")
    except (TypeError, ValueError, OverflowError):
        failure = RetrievalError(
            "Encoder must return finite nonzero 384-dimensional vectors"
        )
    if failure is not None:
        raise failure from None
    return vector


def _embed(encoder, method: str, texts):
    reject_credentials(texts)
    expected = 1 if method == "query_embed" else len(texts)
    try:
        values = list(islice(getattr(encoder, method)(texts), expected + 1))
    except Exception:
        # Local model failures may include source text in diagnostics. The caller
        # gets a generic setup error; no provider or credential data is echoed.
        raise RetrievalError(
            "Local embedding failed; verify the provisioned model and encoder"
        ) from None
    if len(values) != expected:
        raise RetrievalError("Encoder returned an unexpected number of vectors")
    return [_vector(value) for value in values]


def _open_index(
    index_path: Path, *, validate_model: bool = True
) -> tuple[sqlite3.Connection, dict]:
    path = Path(index_path).resolve()
    reject_credentials(str(path))
    if not path.is_file():
        raise RetrievalError("Retrieval index is missing; build it first")
    connection = None
    try:
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        connection.execute("PRAGMA trusted_schema=OFF")
        connection.execute("PRAGMA query_only=ON")
        objects = connection.execute(
            "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view', 'trigger')"
        ).fetchall()
        if set(objects) != {("metadata", "table"), ("chunks", "table")}:
            raise RetrievalError("Unknown retrieval index schema; refusing to use it")
        columns = [row[1] for row in connection.execute("PRAGMA table_info(chunks)")]
        if columns != list(_COLUMNS):
            raise RetrievalError("Unknown retrieval index columns")
        metadata = dict(connection.execute("SELECT key, value FROM metadata"))
        if set(metadata) != _META_KEYS or not all(
            isinstance(value, str) for value in metadata.values()
        ):
            raise RetrievalError("Retrieval index metadata is incomplete")
        reject_credentials(metadata)
        if not 1 <= int(metadata["documents"]) <= int(metadata["chunks"]) <= 20_000:
            raise RetrievalError("Retrieval index counts exceed the supported bounds")
        if metadata["schema_version"] != SCHEMA_VERSION:
            raise RetrievalError("Unknown retrieval index version; refusing to use it")
        expected = {
            "model": MODEL_NAME,
            "dimensions": str(DIMENSIONS),
            "chunk_words": str(CHUNK_WORDS),
            "chunk_overlap": str(CHUNK_OVERLAP),
        }
        if validate_model and any(
            metadata.get(key) != value for key, value in expected.items()
        ):
            raise StaleIndexError(
                "Retrieval model or index format changed; rebuild the index"
            )
        if connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] != int(
            metadata["chunks"]
        ):
            raise RetrievalError("Retrieval index chunk count is inconsistent")
        return connection, metadata
    except RetrievalError:
        if connection is not None:
            connection.close()
        raise
    except (sqlite3.Error, ValueError, TypeError):
        if connection is not None:
            connection.close()
        raise RetrievalError("Retrieval index is invalid; rebuild it") from None


def build_index(corpus_dir: Path, index_path: Path, encoder=None) -> dict:
    """Build an atomic local index; never overwrite an unrelated existing file."""
    corpus_dir, index_path = Path(corpus_dir).resolve(), Path(index_path).resolve()
    reject_credentials([str(corpus_dir), str(index_path)])
    previous = None
    if index_path.exists():
        connection, _ = _open_index(index_path, validate_model=False)
        connection.close()
        previous = index_path.stat()
    documents = _documents(corpus_dir)
    chunks = _chunks(documents)
    encoder = _default_encoder() if encoder is None else encoder
    passages = [
        f"{chunk['title']}\nService: {chunk['service'] or 'general guidance'}\n{chunk['text']}"
        for chunk in chunks
    ]
    vectors = _embed(encoder, "passage_embed", passages)
    if len(vectors) != len(chunks):
        raise RetrievalError("Encoder returned an unexpected number of passage vectors")
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "model": MODEL_NAME,
        "dimensions": str(DIMENSIONS),
        "chunk_words": str(CHUNK_WORDS),
        "chunk_overlap": str(CHUNK_OVERLAP),
        "corpus_dir": str(corpus_dir),
        "corpus_digest": _corpus_digest(documents),
        "documents": str(len(documents)),
        "chunks": str(len(chunks)),
        "encoder_fingerprint": _encoder_identity(encoder),
    }
    reject_credentials(metadata)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=".cra2-index-", suffix=".sqlite", dir=index_path.parent
    )
    os.close(descriptor)
    temporary = Path(temp_name)
    try:
        with sqlite3.connect(temporary) as connection:
            connection.execute(
                "CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE chunks (chunk_id TEXT PRIMARY KEY, doc_id TEXT NOT NULL, title TEXT NOT NULL, source TEXT NOT NULL, kind TEXT NOT NULL, service TEXT, source_dataset TEXT NOT NULL, text TEXT NOT NULL, embedding BLOB NOT NULL)"
            )
            connection.executemany(
                "INSERT INTO metadata VALUES (?, ?)", metadata.items()
            )
            connection.executemany(
                "INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    tuple(chunk[field] for field in _COLUMNS[:-1]) + (vector.tobytes(),)
                    for chunk, vector in zip(chunks, vectors)
                ],
            )
        if previous is None:
            # Publish a new index without clobbering a file created mid-build.
            try:
                os.link(temporary, index_path)
            except FileExistsError:
                raise RetrievalError(
                    "Index destination appeared during the build; it was left unchanged"
                ) from None
        else:
            current = index_path.stat()
            if (
                current.st_dev,
                current.st_ino,
                current.st_size,
                current.st_mtime_ns,
            ) != (
                previous.st_dev,
                previous.st_ino,
                previous.st_size,
                previous.st_mtime_ns,
            ):
                raise RetrievalError(
                    "Index destination changed during the build; it was left unchanged"
                )
            os.replace(temporary, index_path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {
        "documents": len(documents),
        "chunks": len(chunks),
        "incidents": sum(document["kind"] == "incident" for document in documents),
        "model": MODEL_NAME,
        "dimensions": DIMENSIONS,
        "corpus_digest": metadata["corpus_digest"],
    }


def search(
    query: str,
    index_path: Path,
    limit: int = 3,
    encoder=None,
    service: str | None = None,
) -> list[dict]:
    """Rank a small local corpus by normalized cosine similarity; never infer aliases.

    Explicit service scope includes only that exact service and general documents.
    Scores measure embedding similarity, not factual support or calibrated risk.
    """
    import numpy as np

    reject_credentials([query, service])
    if not isinstance(query, str) or not query.strip() or len(query) > 5000:
        raise RetrievalError(
            "Query must be a nonempty string of at most 5,000 characters"
        )
    if type(limit) is not int or not 1 <= limit <= 20:
        raise RetrievalError("Retrieval limit must be an integer from 1 to 20")
    connection, metadata = _open_index(index_path)
    try:
        documents = _documents(Path(metadata["corpus_dir"]))
        if _corpus_digest(documents) != metadata["corpus_digest"]:
            raise StaleIndexError(
                "Corpus content or metadata changed; rebuild the index"
            )
        if service is not None and (
            not isinstance(service, str)
            or service not in {doc["service"] for doc in documents}
        ):
            raise RetrievalError("Service filter must exactly match a source service")
        rows = connection.execute("SELECT * FROM chunks ORDER BY chunk_id").fetchall()
    finally:
        connection.close()
    expected = {
        chunk["chunk_id"]: {
            key: value for key, value in chunk.items() if key in _COLUMNS[:-1]
        }
        for chunk in _chunks(documents)
    }
    if len(rows) != len(expected):
        raise RetrievalError("Index source records changed; rebuild it")
    candidates, vectors = [], []
    for row in rows:
        record = dict(zip(_COLUMNS, row))
        blob = record.pop("embedding")
        reject_credentials(record)
        if record != expected.get(record["chunk_id"]):
            raise RetrievalError("Index source records changed; rebuild it")
        if not isinstance(blob, bytes) or len(blob) != DIMENSIONS * 4:
            raise RetrievalError("Index contains an invalid embedding; rebuild it")
        vector = _vector(np.frombuffer(blob, dtype="<f4"))
        if service is None or record["service"] in (None, service):
            candidates.append(record)
            vectors.append(vector)
    if not candidates:
        return []
    encoder = _default_encoder() if encoder is None else encoder
    if _encoder_identity(encoder) != metadata["encoder_fingerprint"]:
        raise StaleIndexError("Loaded embedding artifacts changed; rebuild the index")
    query_vectors = _embed(encoder, "query_embed", query.strip())
    if len(query_vectors) != 1:
        raise RetrievalError("Encoder must return exactly one query vector")
    scores = np.stack(vectors) @ query_vectors[0]
    ranked = [
        {**record, "score": round(float(np.clip(score, -1, 1)), 6)}
        for record, score in zip(candidates, scores)
    ]
    ranked.sort(key=lambda record: (-record["score"], record["chunk_id"]))
    result = ranked[:limit]
    reject_credentials(result)
    return result
