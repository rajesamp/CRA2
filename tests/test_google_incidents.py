"""Feed normalization is deterministic, bounded and never promotes evidence."""

from copy import deepcopy
import json
from secrets import token_hex

import pytest

from cra2 import config
from cra2.google_incidents import (
    FEED_URL, MAX_FEED_BYTES, GoogleIncidentError, parse_feed, stage_feed, validate_staging,
)
from cra2.public_evidence import load_public_evidence


def update(**changes):
    return {"created": "2026-06-13T10:00:00Z", "modified": "2026-06-13T11:00:00Z",
            "when": "2026-06-13T10:00:00Z", "status": "AVAILABLE",
            "text": "## Incident Report\nSynthetic fixture: a worker configuration change needed rollback.",
            "affected_locations": [{"id": "test-region", "title": "Test region"}], **changes}


def incident(**changes):
    return {"id": "test-incident-1", "uri": "incidents/test-incident-1",
            "begin": "2026-06-12T12:00:00Z", "created": "2026-06-12T12:30:00Z",
            "end": "2026-06-12T13:30:00Z", "modified": "2026-06-13T11:00:00Z",
            "external_desc": "Synthetic Google-shaped incident fixture.",
            "affected_products": [{"id": "product-1", "title": "Original service title"}],
            "severity": "low", "status_impact": "SERVICE_INFORMATION",
            "updates": [update()], "most_recent_update": update(), **changes}


def encoded(*records):
    return json.dumps(list(records)).encode()


def staged(**changes):
    return stage_feed(encoded(incident(**changes)))


def test_exact_shape_provenance_null_risk_and_no_full_reports():
    text = " ".join("fixtureword" + str(n) for n in range(200))
    value = staged(updates=[update(text=text)], most_recent_update=update(text=text))
    row, = value["records"]
    assert set(value) == {"schema_version", "source_url", "records"}
    assert value["schema_version"] == 1 and value["source_url"] == FEED_URL
    assert row["source_url"] == "https://status.cloud.google.com/incidents/test-incident-1"
    assert row["source_severity"] == "low" and row["prospective_cra2_risk"] is None
    assert row["review_status"] == "pending_review" and row["causation"] == "unreviewed"
    assert row["outcome"] == "unverified" and row["narrative_trust"] == "untrusted_source_text"
    assert len(row["narrative_excerpt"].split()) == 80
    assert text not in json.dumps(value) and "fixtureword199" not in json.dumps(value)
    assert row["affected_products"] == [{"id": "product-1", "title": "Original service title"}]
    assert validate_staging(value) == value
    assert validate_staging(value) is not value


def test_missing_optional_fields_and_zero_updates_remain_unknown():
    record = incident()
    for field in ("severity", "status_impact", "end", "updates", "most_recent_update"):
        record.pop(field)
    row, = parse_feed(encoded(record))
    assert row["end"] is row["source_severity"] is row["status_impact"] is row["latest_update"] is None
    assert row["update_count"] == 0 and row["currently_affected_locations"] == []
    assert row["narrative_excerpt"] == record["external_desc"]


def test_pointer_dedup_keeps_richer_location_metadata():
    record = incident()
    record["most_recent_update"].pop("affected_locations")
    row, = parse_feed(encoded(record))
    assert row["update_count"] == 1
    equivalent = deepcopy(record)
    equivalent.pop("most_recent_update")
    assert parse_feed(encoded(equivalent)) == [row]


def test_new_pointer_update_is_preserved_and_latest_edit_selects_excerpt():
    record = incident(most_recent_update=update(modified="2026-06-14T00:00:00Z", text="Revised report fixture."))
    row, = parse_feed(encoded(record))
    assert row["update_count"] == 2 and row["narrative_excerpt"] == "Revised report fixture."
    assert row["revision_at"] == "2026-06-14T00:00:00Z"


def test_revision_hash_captures_unpersisted_text_and_additive_metadata():
    original = incident(updates=[update(text="x " * 100 + "original")], most_recent_update=None)
    baseline, = parse_feed(encoded(original))
    altered = deepcopy(original)
    altered["updates"][0]["text"] = "x " * 100 + "corrected"
    changed, = parse_feed(encoded(altered))
    assert baseline["narrative_excerpt"] == changed["narrative_excerpt"]
    assert baseline["source_revision"] != changed["source_revision"]
    for container in (altered, altered["updates"][0], altered["affected_products"][0],
                      altered["updates"][0]["affected_locations"][0]):
        before = parse_feed(encoded(altered))[0]["source_revision"]
        container["future_source_metadata"] = "retained in hash"
        assert parse_feed(encoded(altered))[0]["source_revision"] != before


def test_ordering_and_repeated_imports_are_idempotent():
    first = incident()
    second = incident(id="a-first", uri="incidents/a-first")
    one = stage_feed(encoded(first, second))
    assert [row["id"] for row in one["records"]] == ["a-first", "test-incident-1"]
    assert stage_feed(encoded(second, first, first), previous=one) == one
    assert stage_feed(b"[]", previous=one) == one
    assert parse_feed(encoded(first, first)) == parse_feed(encoded(first))
    conflict = deepcopy(first)
    conflict["external_desc"] += " Different same-ID source."
    with pytest.raises(GoogleIncidentError):
        parse_feed(encoded(first, conflict))


def test_normalized_dates_keep_offsets_fractional_order_and_missing_end():
    record = incident(begin="2026-06-12T07:00:00-05:00", end=None,
                      created="2026-06-12T12:30:00.000Z")
    row, = parse_feed(encoded(record))
    assert row["begin"] == "2026-06-12T12:00:00Z" and row["created"] == "2026-06-12T12:30:00Z"
    assert row["end"] is None
    older = staged(modified="2026-06-13T11:00:00.100000001Z")
    newer = stage_feed(encoded(incident(modified="2026-06-13T06:00:00.100000002-05:00")), previous=older)
    assert newer["records"][0]["modified"] == "2026-06-13T11:00:00.100000002Z"
    assert stage_feed(encoded(incident(modified="2026-06-13T11:00:00Z")), previous=newer) == newer


def test_early_year_timestamps_keep_four_digits_portably():
    record = incident(begin="0001-01-01T01:00:00+01:00", created="0001-01-01T00:00:00Z",
                      modified="0001-01-01T00:00:00Z", end=None, updates=[], most_recent_update=None)
    value = stage_feed(encoded(record))
    assert value["records"][0]["begin"] == "0001-01-01T00:00:00Z"
    assert validate_staging(value) == value


def test_newer_edited_update_wins_even_with_older_incident_modified():
    before = staged(modified="2026-06-14T12:00:00Z")
    incoming = incident(modified="2026-06-13T11:00:00Z",
        most_recent_update=update(modified="2026-06-15T12:00:00Z", text="Newest edited report fixture."))
    after = stage_feed(encoded(incoming), previous=before)
    assert after["records"][0]["modified"] == "2026-06-13T11:00:00Z"
    assert after["records"][0]["revision_at"] == "2026-06-15T12:00:00Z"
    assert after["records"][0]["narrative_excerpt"] == "Newest edited report fixture."
    assert stage_feed(encoded(incident()), previous=after) == after


def test_same_timestamp_changed_revision_is_pending_and_inputs_unmodified():
    previous = staged()
    prior_copy = deepcopy(previous)
    change = incident(external_desc="Corrected source description.")
    result = stage_feed(encoded(change), previous=previous)
    assert result["records"][0]["source_revision"] != previous["records"][0]["source_revision"]
    assert result["records"][0]["review_status"] == "pending_review"
    assert previous == prior_copy


def test_curated_google_matches_by_official_url_and_stays_separate():
    public = load_public_evidence(config.DATA_DIR)
    source = incident(id="ow5i3PPK96RduMcb1SsW", uri="incidents/ow5i3PPK96RduMcb1SsW")
    value = stage_feed(encoded(source), public_records=public)
    assert value["records"][0]["canonical_record_id"] == "public-google-cloud-2025-06-12"
    assert value["records"][0]["review_status"] == "pending_review"
    assert stage_feed(b"[]", previous=value, public_records=public) == value
    with pytest.raises(GoogleIncidentError):
        stage_feed(encoded(source), public_records=public + [deepcopy(public[0])])


@pytest.mark.parametrize("change", [
    {"id": "../escape"}, {"uri": "https://attacker.invalid/"}, {"uri": "incidents/wrong"},
    {"id": "id%2fslash"}, {"begin": "2026-06-12"}, {"begin": "2026-06-12T12:00:00"},
    {"created": "2026-02-30T00:00:00Z"}, {"modified": "2026-06-12T12:00:00-00:00"},
    {"modified": "2026-06-12T12:00:00+00:60"}, {"end": ""}, {"end": "2020-01-01T00:00:00Z"},
    {"severity": []}, {"status_impact": True}, {"updates": {}},
    {"affected_products": []}, {"affected_products": [{"id": "p", "title": "t"}] * 2},
    {"currently_affected_locations": None}, {"external_desc": "bad\u202etext"},
    {"future_field": "hidden\u200bcontrol"}, {"external_desc": "a" * 4001},
    {"updates": [update(text="x" * 65537)]},
])
def test_known_malformed_source_fields_fail_closed(change):
    with pytest.raises(GoogleIncidentError):
        parse_feed(encoded(incident(**change)))


@pytest.mark.parametrize("raw", [b'{"records":[]}', b'[{"id":"a","id":"b"}]', b'[NaN]',
    b'[1e99999]', b'[] trailing', b'\xff', b'9' * 100, b'[' * 2000 + b']' * 2000,
    b' ' * (MAX_FEED_BYTES + 1)])
def test_invalid_or_oversized_json_is_protected(raw):
    with pytest.raises(GoogleIncidentError, match="^Invalid Google incident"):
        parse_feed(raw)


@pytest.mark.parametrize("field,value", [
    ("review_status", "approved"), ("outcome", "successful_change"), ("causation", "confirmed"),
    ("prospective_cra2_risk", "low"), ("narrative_trust", "trusted"),
    ("source_revision", "forged"), ("revision_at", "2020-01-01T00:00:00Z"),
    ("source_url", "https://other.example/"), ("update_count", True),
    ("latest_update", None), ("canonical_record_id", "checkout-service"),
    ("narrative_excerpt", "x " * 81), ("description", "bad\x00control"),
])
def test_previous_staging_cannot_contain_approved_or_malformed_records(field, value):
    previous = staged()
    previous["records"][0][field] = value
    with pytest.raises(GoogleIncidentError):
        stage_feed(b"[]", previous=previous)


def test_closed_staging_rejects_extra_fields_and_aliases():
    value = staged()
    value["records"][0]["affected_products"][0]["current_title"] = "New marketing name"
    with pytest.raises(GoogleIncidentError):
        validate_staging(value)
    value = staged()
    value["records"][0]["policy"] = {"high_risk": False}
    with pytest.raises(GoogleIncidentError):
        validate_staging(value)


def test_credentials_fail_without_echoing(monkeypatch):
    secret = token_hex(24)
    monkeypatch.setenv("GROQ_API_KEY", secret)
    with pytest.raises(GoogleIncidentError) as caught:
        parse_feed(encoded(incident(external_desc=secret)))
    assert secret not in str(caught.value)


def test_no_live_health_or_success_inferred_from_closed_status():
    row, = parse_feed(encoded(incident()))
    assert row["latest_update"]["status"] == "AVAILABLE"
    assert row["end"] is not None
    assert row["outcome"] == "unverified" and row["causation"] == "unreviewed"
    assert "health" not in row and "service" not in row and "policy" not in row
