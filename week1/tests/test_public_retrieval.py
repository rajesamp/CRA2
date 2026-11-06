"""Public analogues extend retrieval without rewriting local service history."""

from copy import deepcopy
import json
import shutil

import numpy as np
import pytest

from cra2 import config
from cra2.advisor import CATALOG
from cra2.public_evidence import public_documents, validate_public_hit
from week1 import chat, retrieval


class AnalogueEncoder:
    fingerprint = "public-evidence-test-v1"
    terms = ("regular", "expression", "backtracking", "cpu", "prefixes", "cleanup")

    def vector(self, text):
        vector = np.zeros(retrieval.DIMENSIONS, dtype=np.float32)
        words = text.lower().split()
        for i, term in enumerate(self.terms):
            vector[i] = words.count(term)
        vector[-1] = .01
        return vector

    def passage_embed(self, texts):
        return iter(self.vector(text) for text in texts)

    def query_embed(self, query):
        return iter([self.vector(query)])


@pytest.fixture
def index(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "general.md").write_text("# General guidance\nReview rollout safeguards.")
    (corpus / "manifest.json").write_text(json.dumps({"general": {"kind": "runbook", "service": None}}))
    path = tmp_path / "index.sqlite3"
    encoder = AnalogueEncoder()
    retrieval.build_index(corpus, path, encoder=encoder)
    return path, encoder


def test_public_summary_keeps_facts_caveats_and_original_identity_in_one_chunk():
    documents = public_documents()
    chunks = retrieval._chunks(documents)
    assert len(chunks) == len(documents) == 19
    for doc, chunk in zip(documents, chunks):
        assert chunk["text"] == doc["text"]
        assert chunk["service"] not in CATALOG
        validate_public_hit({**chunk, "score": .5})


def test_relevant_analogue_can_rank_without_becoming_local_history(index):
    path, encoder = index
    hits = retrieval.search("checkout-service regular expression backtracking CPU", path,
                            service="checkout-service", encoder=encoder)
    assert len(hits) == 3
    external = [hit for hit in hits if hit["source_dataset"] == "public_corporate"]
    assert len(external) == 1
    hit, = external
    assert hit["doc_id"] == "public-cloudflare-2019-07-02"
    assert hit["service"] == "Cloudflare WAF" and hit["kind"] == "external_incident"
    assert all(h["service"] in (None, "checkout-service") for h in hits if h not in external)
    assert hits == retrieval.search("checkout-service regular expression backtracking CPU", path,
                                    service="checkout-service", encoder=encoder)


@pytest.mark.parametrize("query", ["deployment", "backtracking", "incident review policy",
                                   "configuration rollout", "software update", "production validation"])
def test_external_requires_two_content_terms_even_without_service_scope(index, query):
    path, encoder = index
    hits = retrieval.search(query, path, limit=20, encoder=encoder)
    assert not any(h["source_dataset"] == "public_corporate" for h in hits)


def test_public_source_edits_invalidate_existing_index(index, tmp_path, monkeypatch):
    path, encoder = index
    data = tmp_path / "data"
    shutil.copytree(config.DATA_DIR, data)
    catalog = json.loads((data / "public_evidence.json").read_text())
    catalog["records"][0]["caveats"] += " Recheck source attribution."
    (data / "public_evidence.json").write_text(json.dumps(catalog))
    monkeypatch.setattr(config, "DATA_DIR", data)
    with pytest.raises(retrieval.StaleIndexError, match="Corpus"):
        retrieval.search("regular expression", path, encoder=encoder)


def test_chat_sends_public_plan_as_document_and_keeps_policy_floor():
    document = next(d for d in public_documents() if d["kind"] == "external_change_plan")
    hit = {**document, "chunk_id": document["doc_id"] + "#chunk-001", "score": .9}
    received = []

    def review(payload, _weights):
        received.append(deepcopy(payload))
        return {"out": {"comments": [{"tag": "history", "severity": "low",
            "text": "Which rollback validation covers the worker configuration?",
            "evidence": [hit["chunk_id"]]}]}, "tokens": [1, 1], "cache_hit": False,
            "request_attempted": False}

    answer, trace = chat.respond("Change auth-service worker configuration to increase CPU reservations.",
        mode="Groq assessment", retriever=lambda *_a, **_k: [deepcopy(hit)], reviewer=review)
    payload, = received
    assert payload["incidents"] == [] and payload["documents"] == [hit]
    assert trace["risk_floor"] == "medium"  # configured auth-service policy survives low comment
    assert trace["retrieved"][0]["source_service"] == document["service"]
    assert "External analogue" in answer and "Company source" in answer


def test_chat_rejects_relabelled_public_hit_before_model():
    document = public_documents()[0]
    hit = {**document, "chunk_id": document["doc_id"] + "#chunk-001", "score": .9,
           "service": "checkout-service"}
    with pytest.raises(ValueError):
        chat.respond("Change checkout-service worker configuration to increase CPU reservations.",
            mode="Groq assessment", retriever=lambda *_a, **_k: [hit],
            reviewer=lambda *_a: pytest.fail("Invalid provenance must not reach model"))
