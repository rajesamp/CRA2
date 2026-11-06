"""Reviewed Google additions require rebuilding and retain analogue boundaries."""

from copy import deepcopy
import json
import re

import numpy as np
import pytest

from cra2 import config
from cra2.public_evidence import validate_public_hit
from week1 import retrieval


NEW_GOOGLE_IDS = {
    "public-google-vertex-2026-02-27",
    "public-google-gcve-2026-07-14",
    "public-google-network-2026-08-20",
    "public-google-router-2026-09-01",
    "public-google-storage-2026-10-08",
    "public-google-power-2026-10-20",
}
ROUTER_ID = "public-google-router-2026-09-01"
ROUTER_QUERY = "checkout-service router transceivers fiber sequencing"


class GoogleAnalogueEncoder:
    """Deterministic boundary fixture; these scores are not measured model recall."""

    fingerprint = "reviewed-google-analogue-fixture-v1"
    terms = ("router", "transceivers", "fiber", "sequencing",
             "regular", "expression", "backtracking")

    def vector(self, text):
        words = set(re.findall(r"[a-z]+", text.lower()))
        vector = np.zeros(retrieval.DIMENSIONS, dtype=np.float32)
        for position, term in enumerate(self.terms):
            vector[position] = term in words
        vector[-1] = .01
        return vector

    def passage_embed(self, texts):
        return iter(self.vector(text) for text in texts)

    def query_embed(self, query):
        return iter([self.vector(query)])


@pytest.fixture
def environment(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    for name in ("checkout_system.json", "incidents.json", "sample_incidents.json",
                 "public_evidence.json"):
        (data / name).write_bytes((config.DATA_DIR / name).read_bytes())
    monkeypatch.setattr(config, "DATA_DIR", data)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "general.md").write_text("# Review guidance\nVerify rollout safeguards.")
    (corpus / "manifest.json").write_text(json.dumps({
        "general": {"kind": "runbook", "service": None},
    }))
    return data, corpus, tmp_path / "index.sqlite3", GoogleAnalogueEncoder()


def test_google_additions_invalidate_old_index_until_rebuilt(environment):
    data, corpus, path, encoder = environment
    catalog_path = data / "public_evidence.json"
    expanded_bytes = catalog_path.read_bytes()
    expanded = json.loads(expanded_bytes)
    assert NEW_GOOGLE_IDS <= {record["id"] for record in expanded["records"]}
    prior = deepcopy(expanded)
    prior["records"] = [record for record in prior["records"]
                        if record["id"] not in NEW_GOOGLE_IDS]
    catalog_path.write_text(json.dumps(prior))
    before = retrieval.build_index(corpus, path, encoder=encoder)
    assert not NEW_GOOGLE_IDS.intersection(
        hit["doc_id"] for hit in retrieval.search(
            ROUTER_QUERY, path, service="checkout-service", encoder=encoder)
    )

    catalog_path.write_bytes(expanded_bytes)
    old_index = path.read_bytes()
    with pytest.raises(retrieval.StaleIndexError, match="Corpus"):
        retrieval.search(ROUTER_QUERY, path, service="checkout-service", encoder=encoder)
    assert path.read_bytes() == old_index

    after = retrieval.build_index(corpus, path, encoder=encoder)
    assert after["external_records"] == before["external_records"] + len(NEW_GOOGLE_IDS)
    assert after["incidents"] == before["incidents"]
    assert after["corpus_digest"] != before["corpus_digest"]
    hits = retrieval.search(ROUTER_QUERY, path, service="checkout-service", encoder=encoder)
    external = [hit for hit in hits if hit["source_dataset"] == "public_corporate"]
    hit, = external
    assert hit["doc_id"] == ROUTER_ID
    record = next(record for record in expanded["records"] if record["id"] == ROUTER_ID)
    assert hit["service"] == record["original_service"]
    assert hit["source"] == record["source_url"]
    assert hit["kind"] == "external_incident"
    validate_public_hit(hit)
    assert all(hit["service"] in (None, "checkout-service")
               for hit in hits if hit["source_dataset"] != "public_corporate")
    assert hits == retrieval.search(
        ROUTER_QUERY, path, service="checkout-service", encoder=encoder)


def test_google_analogue_still_caps_external_hits_when_another_source_matches(environment):
    _data, corpus, path, encoder = environment
    retrieval.build_index(corpus, path, encoder=encoder)
    competing_hits = retrieval.search("regular expression", path,
                                      service="checkout-service", encoder=encoder)
    assert [hit["doc_id"] for hit in competing_hits
            if hit["source_dataset"] == "public_corporate"] == ["public-cloudflare-2019-07-02"]
    # Both router terms and the Cloudflare regular-expression terms qualify;
    # the deterministic encoder ranks the four router terms above the latter two.
    hits = retrieval.search(ROUTER_QUERY + " regular expression", path, limit=20,
                            service="checkout-service", encoder=encoder)
    external = [hit for hit in hits if hit["source_dataset"] == "public_corporate"]
    assert [hit["doc_id"] for hit in external] == [ROUTER_ID]
    assert external[0]["service"] == "Google Compute Engine and Virtual Private Cloud (VPC)"


@pytest.mark.parametrize("query", ["configuration rollout", "planned maintenance",
                                   "production validation software update"])
def test_expanded_google_corpus_does_not_admit_generic_overlap(environment, query):
    _data, corpus, path, encoder = environment
    retrieval.build_index(corpus, path, encoder=encoder)
    hits = retrieval.search(query, path, limit=20, encoder=encoder)
    assert not any(hit["source_dataset"] == "public_corporate" for hit in hits)
