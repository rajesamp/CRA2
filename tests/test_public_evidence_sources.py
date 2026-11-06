"""Canonical source URLs are unique identities, without invented URL aliases."""

from copy import deepcopy
import json

import pytest

from cra2 import config
from cra2.public_evidence import PublicEvidenceError, load_public_evidence


@pytest.fixture
def collection(tmp_path):
    for name in ("public_evidence.json", "checkout_system.json"):
        (tmp_path / name).write_bytes((config.DATA_DIR / name).read_bytes())
    return tmp_path


def append_copy(directory, *, source_url=None):
    path = directory / "public_evidence.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    record = deepcopy(data["records"][0])
    record["id"] += "-source-duplicate-test"
    record["reported_facts"] = "A different paraphrase cannot establish a second source identity."
    if source_url is not None:
        record["source_url"] = source_url
    data["records"].append(record)
    path.write_text(json.dumps(data), encoding="utf-8")
    return record


def test_distinct_record_ids_cannot_duplicate_an_official_source_url(collection):
    duplicate = append_copy(collection)
    with pytest.raises(PublicEvidenceError, match="^Invalid public corporate evidence$") as failure:
        load_public_evidence(collection)
    assert duplicate["source_url"] not in str(failure.value)
    assert duplicate["reported_facts"] not in str(failure.value)


def test_checked_in_canonical_source_urls_are_unique():
    records = load_public_evidence()
    urls = [record["source_url"] for record in records]
    assert urls and len(urls) == len(set(urls))


def test_url_spelling_is_preserved_without_new_alias_normalization(collection):
    first = load_public_evidence(collection)[0]
    # Trailing-slash equivalence needs publisher-specific review; this guard
    # only rejects identical strings and does not invent an equivalence rule.
    alternate = first["source_url"].rstrip("/") if first["source_url"].endswith("/") else first["source_url"] + "/"
    appended = append_copy(collection, source_url=alternate)
    records = load_public_evidence(collection)
    by_id = {record["id"]: record for record in records}
    assert by_id[first["id"]]["source_url"] == first["source_url"]
    assert by_id[appended["id"]]["source_url"] == alternate
    assert by_id[appended["id"]]["original_service"] == first["original_service"]
