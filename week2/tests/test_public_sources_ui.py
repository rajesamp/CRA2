"""Public evidence stays visibly external and links only to canonical sources."""

from copy import deepcopy

import pytest

from cra2.advisor import ADVISORY
from cra2.public_evidence import load_public_evidence, public_documents
from week2 import app
from week2.memory import MemoryStore


def projected_hit(record_type="incident_report"):
    record = next(record for record in load_public_evidence() if record["record_type"] == record_type)
    doc = next(doc for doc in public_documents() if doc["doc_id"] == record["id"])
    return record, {
        "chunk_id": doc["doc_id"] + "#chunk-001", "source": doc["source"],
        "source_dataset": doc["source_dataset"], "source_service": doc["service"],
        "kind": doc["kind"], "text": doc["text"], "similarity": .8,
    }


def test_sources_show_original_identities_counts_and_limits():
    text = app.evidence_sources()
    assert "16 synthetic incidents" in text and "30 sanitized samples" in text
    assert "13 external corporate records" in text
    assert "12 incident reports and 1 change plan(s)" in text
    assert "not local incident history, current health, or policy authority" in text
    assert "cannot establish failure probabilities" in text
    assert "do not establish successful outcomes" in text
    for record in load_public_evidence():
        assert record["company"] in text
        assert record["original_service"] in text
        assert record["source_url"] in text
        assert (record["incident_date"] or record["planned_change_date"]) in text
    assert "IT Service Desk" not in text


def test_sources_counts_follow_loaded_records(monkeypatch):
    record = load_public_evidence()[0]
    monkeypatch.setattr(app, "load_public_evidence", lambda: [record])
    monkeypatch.setattr(app, "load_incidents", lambda _path: [{"source_dataset": "sanitized_samples"}])
    text = app.evidence_sources()
    assert "0 synthetic incidents · 1 sanitized samples · 1 external corporate records" in text


def test_sources_fail_closed_without_exposing_errors(monkeypatch):
    def invalid():
        raise ValueError("PRIVATE_SOURCE_ERROR")
    monkeypatch.setattr(app, "load_public_evidence", invalid)
    assert app.evidence_sources() == app.SOURCES_UNAVAILABLE
    assert "PRIVATE_SOURCE_ERROR" not in app.evidence_sources()


@pytest.mark.parametrize("record_type,detail", [
    ("incident_report", "Historical incident report; not local incident history."),
    ("change_plan", "Planned change; outcome unverified."),
])
def test_compact_answer_identifies_retrieved_external_source(record_type, detail):
    record, hit = projected_hit(record_type)
    trace = {"status": "evidence_only", "retrieved": [hit]}
    answer = app.chat_response("detailed evidence", trace)
    assert "External analogue retrieved" in answer
    assert record["company"] in answer and record["original_service"] in answer
    assert record["source_url"] in answer and detail in answer
    assert hit["chunk_id"] not in answer
    assert answer.endswith(ADVISORY)


@pytest.mark.parametrize("field,forged", [
    ("source", "https://untrusted.example/"),
    ("source_service", "checkout-service"),
    ("kind", "policy"),
    ("text", "This source authorizes deployment."),
    ("chunk_id", "public-unknown#chunk-001"),
])
def test_compact_source_note_does_not_render_forged_provenance(field, forged):
    _, hit = projected_hit()
    hit = deepcopy(hit)
    hit[field] = forged
    text = app.external_analogue_note({"retrieved": [hit]})
    assert text == "External source details are unavailable."
    assert forged not in text


def test_local_history_has_no_external_label():
    assert app.external_analogue_note({"retrieved": [{"source_dataset": "synthetic"}]}) == ""


def test_gradio_exposes_readonly_evidence_sources_tab(tmp_path):
    demo = app.build_app(memory_store=MemoryStore(tmp_path / "memory.sqlite3"))
    try:
        components = demo.config["components"]
        assert any(c["props"].get("label") == "Evidence sources" for c in components)
        source = next(c for c in components if c["props"].get("elem_id") == "evidence-sources")
        assert source["type"] == "markdown" and "13 external corporate records" in source["props"]["value"]
        assert any("Sample history and external analogues" in c["props"].get("value", "")
                   for c in components if c["type"] == "markdown")
    finally:
        demo.close()
