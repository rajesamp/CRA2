"""Local retrieval/index correctness; injected vectors keep all tests offline."""

import hashlib
import io
import json
import sqlite3
import tarfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from week1 import retrieval, setup_index


class FakeEncoder:
    fingerprint = "offline-fixture-v1"

    def __init__(self):
        self.passages = []
        self.queries = []

    @staticmethod
    def vector(text):
        result = np.zeros(retrieval.DIMENSIONS, dtype=np.float32)
        for index, term in enumerate(("alpha", "beta", "gamma")):
            result[index] = text.lower().split().count(term)
        result[-1] = 0.1
        return result

    def passage_embed(self, texts):
        self.passages.extend(texts)
        return iter(self.vector(text) for text in texts)

    def query_embed(self, query):
        self.queries.append(query)
        return iter([self.vector(query)])


@pytest.fixture
def corpus(tmp_path):
    directory = tmp_path / "corpus"
    directory.mkdir()
    docs = {
        "pm-alpha": (
            "postmortem",
            "checkout-service",
            "# Alpha postmortem\n" + "alpha " * 340,
        ),
        "rb-beta": (
            "runbook",
            "payment-gateway",
            "# Beta operations\n\nbeta validation.",
        ),
        "policy-general": (
            "policy",
            None,
            "# General review policy\n\nalpha gamma verification guidance.",
        ),
    }
    manifest = {}
    for name, (kind, service, text) in docs.items():
        (directory / (name + ".md")).write_text(text, encoding="utf-8")
        manifest[name] = {"kind": kind, "service": service}
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return directory


@pytest.fixture
def index(corpus, tmp_path):
    path = tmp_path / "index.sqlite"
    encoder = FakeEncoder()
    counts = retrieval.build_index(corpus, path, encoder=encoder)
    return path, encoder, counts


def metadata(path):
    with sqlite3.connect(path) as connection:
        return dict(connection.execute("SELECT key, value FROM metadata"))


def test_build_ingests_all_original_incidents_and_explicit_markdown(index):
    path, encoder, counts = index
    assert counts["incidents"] == 46 and counts["documents"] == 49
    assert counts["chunks"] == len(encoder.passages) > counts["documents"]
    assert counts["dimensions"] == 384
    assert metadata(path)["model"] == "BAAI/bge-small-en-v1.5"
    assert metadata(path)["encoder_fingerprint"] == "injected:offline-fixture-v1"
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT service, source_dataset, source, text FROM chunks WHERE doc_id='INC-4913'"
        ).fetchone()
        assert row[0] == "payment" and row[1] == "sanitized_samples"
        assert row[2].endswith("data/sample_incidents.json#INC-4913")
        assert "Source label: internal" in row[3]
        for (blob,) in connection.execute("SELECT embedding FROM chunks"):
            assert len(blob) == 384 * 4
            vector = np.frombuffer(blob, dtype="<f4")
            assert np.isfinite(vector).all()
            assert np.linalg.norm(vector) == pytest.approx(1)


def test_chunk_windows_are_bounded_overlapping_and_cover_last_word():
    document = {"doc_id": "window", "text": " ".join(f"word{i}" for i in range(351))}
    chunks = retrieval._chunks([document])
    assert all(len(chunk["text"].split()) <= 160 for chunk in chunks)
    assert chunks[0]["text"].split()[-30:] == chunks[1]["text"].split()[:30]
    assert chunks[-1]["text"].split()[-1] == "word350"
    assert len({chunk["chunk_id"] for chunk in chunks}) == len(chunks)


def test_search_ranks_vectors_and_uses_query_encoder(index):
    path, encoder, _ = index
    result = retrieval.search("alpha", path, encoder=encoder)
    assert len(result) == 3
    assert result[0]["doc_id"] == "pm-alpha"
    assert result[0]["score"] >= result[-1]["score"]
    assert all(-1 <= row["score"] <= 1 for row in result)
    assert encoder.queries == ["alpha"]
    assert {
        "chunk_id",
        "doc_id",
        "text",
        "source",
        "score",
        "kind",
        "service",
        "source_dataset",
        "title",
    } <= result[0].keys()
    assert not any(
        Path(row["source"].split("#")[0]).is_absolute() or ".." in row["source"]
        for row in result
    )
    assert result == retrieval.search("alpha", path, encoder=encoder)


def test_explicit_service_scope_keeps_general_guidance_without_aliases(index):
    path, encoder, _ = index
    result = retrieval.search(
        "alpha gamma", path, limit=20, encoder=encoder, service="checkout-service"
    )
    assert any(row["service"] is None for row in result)
    assert all(row["service"] in (None, "checkout-service") for row in result)
    payment = retrieval.search(
        "beta", path, limit=20, encoder=encoder, service="payment"
    )
    assert all(row["service"] in (None, "payment") for row in payment)
    assert not any(row["service"] == "payment-gateway" for row in payment)
    with pytest.raises(retrieval.RetrievalError, match="exactly"):
        retrieval.search("alpha", path, encoder=encoder, service="guessed-checkout")


@pytest.mark.parametrize("change", ["text", "manifest", "incidents"])
def test_source_changes_fail_stale_before_query_embedding(
    index, corpus, monkeypatch, change
):
    path, encoder, _ = index
    if change == "text":
        (corpus / "pm-alpha.md").write_text(
            "# Changed title\n\nNew content.", encoding="utf-8"
        )
    elif change == "manifest":
        manifest = json.loads((corpus / "manifest.json").read_text())
        manifest["policy-general"]["service"] = "checkout-service"
        (corpus / "manifest.json").write_text(json.dumps(manifest))
    else:
        original = retrieval.load_incidents

        def changed(directory):
            rows = original(directory)
            rows[0]["root_cause"] += " Source correction."
            return rows

        monkeypatch.setattr(retrieval, "load_incidents", changed)
    with pytest.raises(retrieval.StaleIndexError):
        retrieval.search("alpha", path, encoder=encoder)
    assert encoder.queries == []


def test_model_identity_changes_require_rebuild_but_known_index_can_be_rebuilt(
    index, corpus
):
    path, _, _ = index
    encoder = FakeEncoder()
    encoder.fingerprint = "offline-fixture-v2"
    with pytest.raises(retrieval.StaleIndexError, match="artifacts"):
        retrieval.search("alpha", path, encoder=encoder)
    assert encoder.queries == []
    retrieval.build_index(corpus, path, encoder=encoder)
    assert retrieval.search("alpha", path, encoder=encoder)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE metadata SET value='old-model' WHERE key='model'")
    with pytest.raises(retrieval.StaleIndexError):
        retrieval.search("alpha", path, encoder=encoder)
    retrieval.build_index(corpus, path, encoder=encoder)
    assert metadata(path)["model"] == retrieval.MODEL_NAME


def test_unknown_database_is_not_executed_or_overwritten(corpus, tmp_path):
    path = tmp_path / "unrelated.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE important_data (value TEXT)")
        connection.execute("INSERT INTO important_data VALUES ('preserve this')")
    before = path.read_bytes()
    encoder = FakeEncoder()
    with pytest.raises(retrieval.RetrievalError, match="Unknown"):
        retrieval.build_index(corpus, path, encoder=encoder)
    with pytest.raises(retrieval.RetrievalError, match="Unknown"):
        retrieval.search("alpha", path, encoder=encoder)
    assert path.read_bytes() == before
    assert not encoder.passages and not encoder.queries


def test_unknown_version_and_views_are_rejected(index):
    path, encoder, _ = index
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE metadata SET value='999' WHERE key='schema_version'")
    with pytest.raises(retrieval.RetrievalError, match="Unknown"):
        retrieval.search("alpha", path, encoder=encoder)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE metadata SET value='1' WHERE key='schema_version'")
        connection.execute("CREATE VIEW unexpected_view AS SELECT text FROM chunks")
    with pytest.raises(retrieval.RetrievalError, match="Unknown"):
        retrieval.search("alpha", path, encoder=encoder)


@pytest.mark.parametrize(
    "vector",
    [
        np.zeros(384),
        np.ones(383),
        np.ones((1, 384)),
        np.full(384, np.nan),
        np.full(384, np.inf),
    ],
)
def test_invalid_embedding_vectors_are_rejected_before_index_write(
    corpus, tmp_path, vector
):
    class InvalidEncoder(FakeEncoder):
        def passage_embed(self, texts):
            return iter(vector for _ in texts)

    path = tmp_path / "index.sqlite"
    with pytest.raises(retrieval.RetrievalError, match="vectors"):
        retrieval.build_index(corpus, path, encoder=InvalidEncoder())
    assert not path.exists()


def test_wrong_vector_count_does_not_replace_existing_index(index, corpus):
    path, _, _ = index
    before = path.read_bytes()

    class EmptyEncoder(FakeEncoder):
        def passage_embed(self, texts):
            return iter([])

    with pytest.raises(retrieval.RetrievalError, match="number"):
        retrieval.build_index(corpus, path, encoder=EmptyEncoder())
    assert path.read_bytes() == before


def test_corrupted_vector_blob_is_not_used(index):
    path, encoder, _ = index
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE chunks SET embedding=? WHERE chunk_id=(SELECT MIN(chunk_id) FROM chunks)",
            (b"invalid",),
        )
    with pytest.raises(retrieval.RetrievalError, match="embedding"):
        retrieval.search("alpha", path, encoder=encoder)
    assert encoder.queries == []


@pytest.mark.parametrize(
    "patch",
    [
        {"kind": "invented", "service": None},
        {"kind": "runbook", "service": "unknown-service"},
        {"kind": "runbook", "service": []},
        {"kind": "postmortem", "service": None},
    ],
)
def test_manifest_metadata_requires_explicit_supported_values(corpus, tmp_path, patch):
    manifest = json.loads((corpus / "manifest.json").read_text())
    manifest["pm-alpha"] = patch
    (corpus / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(retrieval.RetrievalError):
        retrieval.build_index(corpus, tmp_path / "index.sqlite", encoder=FakeEncoder())


def test_manifest_coverage_and_symlink_boundaries_are_checked(corpus, tmp_path):
    encoder = FakeEncoder()
    (corpus / "unregistered.md").write_text("# Unregistered\nText")
    with pytest.raises(retrieval.RetrievalError, match="exactly"):
        retrieval.build_index(corpus, tmp_path / "index.sqlite", encoder=encoder)
    (corpus / "unregistered.md").unlink()
    outside = tmp_path / "outside.md"
    outside.write_text("# Outside\nNo import allowed")
    (corpus / "pm-alpha.md").unlink()
    (corpus / "pm-alpha.md").symlink_to(outside)
    with pytest.raises(retrieval.RetrievalError, match="inside"):
        retrieval.build_index(corpus, tmp_path / "index.sqlite", encoder=encoder)
    assert encoder.passages == []


@pytest.mark.parametrize(
    "query,limit",
    [("", 3), ("x" * 5001, 3), ("alpha", 0), ("alpha", True), ("alpha", 21)],
)
def test_bad_queries_or_limits_fail_before_embedding(index, query, limit):
    path, encoder, _ = index
    with pytest.raises(retrieval.RetrievalError):
        retrieval.search(query, path, limit=limit, encoder=encoder)
    assert encoder.queries == []


def test_known_credential_never_enters_embedding_or_index(
    corpus, tmp_path, monkeypatch
):
    sentinel = "gsk_RETRIEVAL_FAKE_SENTINEL_NOT_A_REAL_KEY"
    monkeypatch.setenv("GROQ_API_KEY", sentinel)
    (corpus / "pm-alpha.md").write_text("# Private\n" + sentinel)
    encoder = FakeEncoder()
    path = tmp_path / "index.sqlite"
    with pytest.raises(ValueError) as caught:
        retrieval.build_index(corpus, path, encoder=encoder)
    assert sentinel not in str(caught.value)
    assert encoder.passages == [] and not path.exists()


def test_known_credential_in_query_or_stored_text_never_returns(index, monkeypatch):
    path, encoder, _ = index
    sentinel = "gsk_RETRIEVAL_FAKE_SENTINEL_NOT_A_REAL_KEY"
    monkeypatch.setenv("GROQ_API_KEY", sentinel)
    with pytest.raises(ValueError):
        retrieval.search(sentinel, path, encoder=encoder)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE chunks SET text=? WHERE chunk_id=(SELECT MIN(chunk_id) FROM chunks)",
            (sentinel,),
        )
    with pytest.raises(ValueError) as caught:
        retrieval.search("alpha", path, encoder=encoder)
    assert sentinel not in str(caught.value) and encoder.queries == []


def test_offline_injection_never_constructs_real_encoder(corpus, tmp_path, monkeypatch):
    monkeypatch.setattr(
        retrieval,
        "_default_encoder",
        lambda: pytest.fail("Offline tests must not load or download a model"),
    )
    encoder = FakeEncoder()
    path = tmp_path / "index.sqlite"
    retrieval.build_index(corpus, path, encoder=encoder)
    assert retrieval.search("alpha", path, encoder=encoder)


def test_default_encoder_is_local_only_and_fingerprints_loaded_artifacts(
    tmp_path, monkeypatch
):
    import fastembed

    directory = tmp_path / "model"
    directory.mkdir()
    (directory / "model_optimized.onnx").write_bytes(b"fake ONNX fixture")
    (directory / "tokenizer.json").write_text("{}")
    calls = []

    def construct(**options):
        calls.append(options)
        return SimpleNamespace(
            model=SimpleNamespace(
                _model_dir=directory,
                model_description=SimpleNamespace(model_file="model_optimized.onnx"),
            )
        )

    monkeypatch.setattr(fastembed, "TextEmbedding", construct)
    monkeypatch.setattr(retrieval, "LOCAL_MODEL_DIR", directory)
    retrieval._default_encoder.cache_clear()
    try:
        first = retrieval._default_encoder()._cra2_fingerprint
        assert calls[0]["local_files_only"] is True
        assert calls[0]["threads"] == 2
        assert calls[0]["specific_model_path"] == str(directory)
        assert calls[0]["model_name"] == retrieval.MODEL_NAME
        (directory / "tokenizer.json").write_text('{"changed":true}')
        retrieval._default_encoder.cache_clear()
        assert retrieval._default_encoder()._cra2_fingerprint != first
    finally:
        retrieval._default_encoder.cache_clear()


def test_model_setup_requires_explicit_download_and_preserves_existing_files(
    tmp_path, monkeypatch
):
    cache = tmp_path / "models"
    monkeypatch.setattr(retrieval, "MODEL_CACHE", cache)
    monkeypatch.setattr(
        setup_index,
        "urlopen",
        lambda *args, **kwargs: pytest.fail("Unexpected network access"),
    )
    with pytest.raises(retrieval.RetrievalError, match="download-model"):
        setup_index.provision_model()
    assert not cache.exists()
    existing = cache / setup_index.MODEL_FOLDER
    existing.mkdir(parents=True)
    sentinel = existing / "important.txt"
    sentinel.write_text("Existing unrelated content")
    with pytest.raises(retrieval.RetrievalError, match="left unchanged"):
        setup_index.provision_model(download=True)
    assert sentinel.read_text() == "Existing unrelated content"


def test_setup_rejects_wrong_archive_checksum_without_extracting(tmp_path, monkeypatch):
    monkeypatch.setattr(retrieval, "MODEL_CACHE", tmp_path)
    (tmp_path / (setup_index.MODEL_FOLDER + ".tar.gz")).write_bytes(b"not the model")
    monkeypatch.setattr(
        setup_index,
        "urlopen",
        lambda *args, **kwargs: pytest.fail("Unexpected network access"),
    )
    with pytest.raises(retrieval.RetrievalError, match="checksum"):
        setup_index.provision_model()
    assert not (tmp_path / setup_index.MODEL_FOLDER).exists()


@pytest.mark.parametrize(
    "kind", ["traversal", "symlink", "hardlink", "absolute", "duplicate"]
)
def test_safe_archive_extraction_rejects_unsafe_members(tmp_path, monkeypatch, kind):
    archive = tmp_path / "model.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        member = tarfile.TarInfo(f"{setup_index.MODEL_FOLDER}/config.json")
        member.size = 2
        if kind == "traversal":
            member.name = f"{setup_index.MODEL_FOLDER}/../outside.txt"
        if kind == "absolute":
            member.name = "/outside.txt"
        if kind == "symlink":
            member.type, member.linkname = tarfile.SYMTYPE, "/outside.txt"
        if kind == "hardlink":
            member.type, member.linkname = tarfile.LNKTYPE, "/outside.txt"
        bundle.addfile(member, io.BytesIO(b"{}") if member.isfile() else None)
        if kind == "duplicate":
            bundle.addfile(member, io.BytesIO(b"{}"))
    monkeypatch.setattr(setup_index, "_verify_archive", lambda path: None)
    with pytest.raises(retrieval.RetrievalError, match="unsafe"):
        setup_index._extract_archive(archive, tmp_path)
    assert not (tmp_path / setup_index.MODEL_FOLDER).exists()
    assert not (tmp_path / "outside.txt").exists()


def test_verified_local_archive_installs_without_network_and_reuses_verified_files(
    tmp_path, monkeypatch
):
    filename, content = "model_optimized.onnx", b"small offline model fixture"
    monkeypatch.setattr(
        setup_index, "ARTIFACT_SHA256", {filename: hashlib.sha256(content).hexdigest()}
    )
    monkeypatch.setattr(retrieval, "MODEL_CACHE", tmp_path)
    archive = tmp_path / f"{setup_index.MODEL_FOLDER}.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        member = tarfile.TarInfo(f"{setup_index.MODEL_FOLDER}/{filename}")
        member.size = len(content)
        bundle.addfile(member, io.BytesIO(content))
    monkeypatch.setattr(setup_index, "ARCHIVE_BYTES", archive.stat().st_size)
    monkeypatch.setattr(
        setup_index, "ARCHIVE_SHA256", hashlib.sha256(archive.read_bytes()).hexdigest()
    )
    monkeypatch.setattr(
        setup_index,
        "urlopen",
        lambda *args, **kwargs: pytest.fail("Unexpected network access"),
    )
    directory = setup_index.provision_model()
    assert (directory / filename).read_bytes() == content
    assert setup_index.provision_model(download=True) == directory
    (directory / filename).write_bytes(b"tampered")
    with pytest.raises(retrieval.RetrievalError, match="checksum"):
        setup_index.provision_model()


def test_pinned_legacy_tokenizer_limit_is_normalized_and_verified(
    tmp_path, monkeypatch
):
    original = json.dumps(
        {"model_max_length": 1000000000000000019884624838656}
    ).encode()
    installed = (
        json.dumps({"model_max_length": 512}, sort_keys=True, indent=2) + "\n"
    ).encode()
    tokenizer = tmp_path / "tokenizer_config.json"
    tokenizer.write_bytes(original)
    monkeypatch.setattr(
        setup_index,
        "ARTIFACT_SHA256",
        {tokenizer.name: hashlib.sha256(original).hexdigest()},
    )
    monkeypatch.setattr(
        setup_index, "TOKENIZER_INSTALLED_SHA256", hashlib.sha256(installed).hexdigest()
    )
    setup_index._prepare_model(tmp_path)
    assert tokenizer.read_bytes() == installed
    setup_index._prepare_model(tmp_path)
    assert tokenizer.read_bytes() == installed


@pytest.mark.parametrize(
    "field,value",
    [
        ("text", "Altered text absent from cited source"),
        ("source", "data/unrelated.json#bogus"),
        ("chunk_id", "unknown#chunk-001"),
    ],
)
def test_index_rows_must_match_authoritative_source_chunks(index, field, value):
    path, encoder, _ = index
    with sqlite3.connect(path) as connection:
        connection.execute(
            f"UPDATE chunks SET {field}=? WHERE chunk_id=(SELECT MIN(chunk_id) FROM chunks)",
            (value,),
        )
    with pytest.raises(retrieval.RetrievalError, match="source records"):
        retrieval.search("alpha", path, encoder=encoder)
    assert encoder.queries == []


def test_file_created_during_embedding_is_not_overwritten(corpus, tmp_path):
    path = tmp_path / "index.sqlite"

    class ConcurrentEncoder(FakeEncoder):
        def passage_embed(self, texts):
            path.write_bytes(b"unrelated concurrently created file")
            return super().passage_embed(texts)

    with pytest.raises(retrieval.RetrievalError, match="appeared"):
        retrieval.build_index(corpus, path, encoder=ConcurrentEncoder())
    assert path.read_bytes() == b"unrelated concurrently created file"


def test_explicit_download_fetches_only_the_pinned_public_archive(
    tmp_path, monkeypatch
):
    content, filename = b"offline model download fixture", "model_optimized.onnx"
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w:gz") as bundle:
        member = tarfile.TarInfo(f"{setup_index.MODEL_FOLDER}/{filename}")
        member.size = len(content)
        bundle.addfile(member, io.BytesIO(content))
    payload = archive.getvalue()
    monkeypatch.setattr(retrieval, "MODEL_CACHE", tmp_path / "cache")
    monkeypatch.setattr(
        setup_index, "ARTIFACT_SHA256", {filename: hashlib.sha256(content).hexdigest()}
    )
    monkeypatch.setattr(setup_index, "ARCHIVE_BYTES", len(payload))
    monkeypatch.setattr(
        setup_index, "ARCHIVE_SHA256", hashlib.sha256(payload).hexdigest()
    )
    monkeypatch.setenv("GROQ_API_KEY", "gsk_FAKE_SETUP_SENTINEL_NOT_A_REAL_KEY")
    calls = []

    class Response(io.BytesIO):
        def geturl(self):
            return setup_index.MODEL_URL

    def download(url, *, timeout):
        calls.append((url, timeout))
        return Response(payload)

    monkeypatch.setattr(setup_index, "urlopen", download)
    directory = setup_index.provision_model(download=True)
    assert (directory / filename).read_bytes() == content
    assert calls == [(setup_index.MODEL_URL, 30)]
    assert setup_index.provision_model() == directory
    assert len(calls) == 1
