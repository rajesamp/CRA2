"""Pure normalization of Google incident feeds into unreviewed local candidates.

No network, clock, catalog mutation, source promotion or risk scoring occurs
here. Full update narratives contribute to revision hashes, but only one short
untrusted excerpt per incident is retained for human review.
"""

import hashlib
import json
import math
import re
import unicodedata
from copy import deepcopy
from datetime import datetime, timezone

from cra2.secrets import reject_credentials

FEED_URL = "https://status.cloud.google.com/incidents.json"
MAX_FEED_BYTES = MAX_STAGING_BYTES = 4 * 1024 * 1024
MAX_STAGED_RECORDS = 1000
MAX_UPDATES = 256
MAX_TEXT = 65536
MAX_EXCERPT_WORDS = 80
MAX_EXCERPT_CHARS = 1600
_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
_PUBLIC_ID = re.compile(r"public-[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_TIME = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?(Z|[+-]\d{2}:\d{2})\Z")
_RECORD_FIELDS = {
    "id", "source_url", "begin", "created", "end", "modified", "revision_at", "description",
    "affected_products", "currently_affected_locations", "previously_affected_locations",
    "source_severity", "status_impact", "source_revision", "update_count", "latest_update",
    "narrative_excerpt", "narrative_trust", "review_status", "causation", "outcome",
    "prospective_cra2_risk", "canonical_record_id",
}
_LATEST_FIELDS = {"created", "modified", "when", "status", "digest"}
_LABELS = {"narrative_trust": "untrusted_source_text", "review_status": "pending_review",
           "causation": "unreviewed", "outcome": "unverified", "prospective_cra2_risk": None}


class GoogleIncidentError(ValueError):
    """Protected error that never echoes source input or credentials."""


def _fail():
    raise GoogleIncidentError("Invalid Google incident feed or staging data") from None


def _guard(value):
    try:
        reject_credentials(value)
    except (ValueError, TypeError, RecursionError):
        _fail()


def _source_tree(value):
    if isinstance(value, str):
        _text(value, MAX_FEED_BYTES, empty=True, multiline=True)
    elif isinstance(value, dict):
        for key, item in value.items():
            _text(key, 200)
            _source_tree(item)
    elif isinstance(value, list):
        for item in value:
            _source_tree(item)


def _text(value, maximum, *, empty=False, multiline=False):
    if (not isinstance(value, str) or len(value) > maximum
            or (not empty and not value.strip())
            or any(unicodedata.category(c).startswith("C")
                   and not (multiline and c in "\n\r\t") for c in value)):
        _fail()
    return value


def _timestamp(value):
    _text(value, 40)
    match = _TIME.fullmatch(value)
    if match is None:
        _fail()
    base, fraction, offset = match.groups()
    if offset == "-00:00" or (offset != "Z" and (int(offset[1:3]) > 23 or int(offset[4:]) > 59)):
        _fail()
    try:
        moment = datetime.fromisoformat(base + ("+00:00" if offset == "Z" else offset)).astimezone(timezone.utc)
    except (ValueError, OverflowError):
        _fail()
    fraction = (fraction or "").rstrip("0")
    # isoformat preserves four-digit years even where libc strftime('%Y') does
    # not. The normalized moment is UTC, so strip only its known '+00:00'.
    return moment.isoformat(timespec="seconds")[:-6] + ("." + fraction if fraction else "") + "Z"


def _time_key(value):
    # Canonical UTC timestamps compare by whole seconds, then nanoseconds.
    return value[:19], (value[20:-1] if "." in value else "").ljust(9, "0")


def _serialized(value, maximum=MAX_STAGING_BYTES):
    try:
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        if len(raw) > maximum:
            _fail()
        return raw
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        _fail()


def _digest(value):
    return hashlib.sha256(_serialized(value, MAX_FEED_BYTES)).hexdigest()


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            _fail()
        value[key] = item
    return value


def _integer(value):
    if len(value) > 20:
        _fail()
    return int(value)


def _float(value):
    if len(value) > 100:
        _fail()
    number = float(value)
    if not math.isfinite(number):
        _fail()
    return number


def _identities(value, *, allow_empty=True):
    if not isinstance(value, list) or len(value) > 200 or (not allow_empty and not value):
        _fail()
    seen, normalized = set(), []
    for item in value:
        if not isinstance(item, dict) or not {"id", "title"} <= item.keys():
            _fail()
        identity = _text(item["id"], 128)
        title = _text(item["title"], 300)
        if not _ID.fullmatch(identity) or identity in seen:
            _fail()
        if "current_title" in item:
            _text(item["current_title"], 300)
        seen.add(identity)
        normalized.append({"id": identity, "title": title})
    return sorted(normalized, key=lambda item: item["id"])


def _optional_text(value, limit):
    return None if value is None else _text(value, limit)


def _source_identities(value):
    _identities(value)
    return sorted(deepcopy(value), key=lambda item: item["id"])


def _update(value):
    required = {"created", "modified", "when", "text", "status"}
    if not isinstance(value, dict) or not required <= value.keys():
        _fail()
    normalized = deepcopy(value)
    for field in ("created", "modified", "when"):
        normalized[field] = _timestamp(value[field])
    normalized["text"] = _text(value["text"], MAX_TEXT, empty=True, multiline=True)
    normalized["status"] = _text(value["status"], 100)
    normalized["affected_locations"] = _source_identities(value.get("affected_locations", []))
    return normalized


def _excerpt(value):
    words, count, selected = value.split(), 0, []
    for word in words[:MAX_EXCERPT_WORDS]:
        if count + len(word) + bool(selected) > MAX_EXCERPT_CHARS:
            break
        selected.append(word)
        count += len(word) + (len(selected) > 1)
    return " ".join(selected)


def _normalize(record):
    required = {"id", "uri", "begin", "created", "modified", "external_desc", "affected_products"}
    if not isinstance(record, dict) or not required <= record.keys():
        _fail()
    identity = _text(record["id"], 128)
    if not _ID.fullmatch(identity) or record["uri"] != "incidents/" + identity:
        _fail()
    times = {field: _timestamp(record[field]) for field in ("begin", "created", "modified")}
    end = None if record.get("end") is None else _timestamp(record["end"])
    if end is not None and _time_key(end) < _time_key(times["begin"]):
        _fail()
    description = _text(record["external_desc"], 4000, multiline=True)
    products = _identities(record["affected_products"], allow_empty=False)
    locations = {field: _identities(record.get(field, [])) for field in (
        "currently_affected_locations", "previously_affected_locations")}
    updates = record.get("updates", [])
    if not isinstance(updates, list) or len(updates) > MAX_UPDATES:
        _fail()
    by_digest = {_digest(item): item for item in (_update(value) for value in updates)}
    if record.get("most_recent_update") is not None:
        recent = _update(record["most_recent_update"])
        supplied = set(record["most_recent_update"])
        if not any(all(item.get(key) == recent[key] for key in supplied) for item in by_digest.values()):
            by_digest[_digest(recent)] = recent
    if len(by_digest) > MAX_UPDATES:
        _fail()
    ordered = sorted(by_digest.items(), key=lambda pair: (
        _time_key(pair[1]["modified"]), _time_key(pair[1]["when"]),
        _time_key(pair[1]["created"]), pair[0]))
    latest_digest, latest = ordered[-1] if ordered else (None, None)
    revision_at = max([times["modified"], *[item["modified"] for _, item in ordered]], key=_time_key)
    source = deepcopy(record)
    source.pop("most_recent_update", None)
    source.update(times, end=end, external_desc=description, updates=[item for _, item in ordered],
                  severity=_optional_text(record.get("severity"), 100),
                  status_impact=_optional_text(record.get("status_impact"), 100),
                  **{field: _source_identities(record.get(field, [])) for field in locations})
    # Keep optional source metadata (e.g. marketing title changes) in the hash.
    source["affected_products"] = sorted(record["affected_products"], key=lambda item: item["id"])
    return {"id": identity, "source_url": "https://status.cloud.google.com/incidents/" + identity,
            **times, "revision_at": revision_at, "end": end, "description": description, "affected_products": products, **locations,
            "source_severity": source["severity"], "status_impact": source["status_impact"],
            "source_revision": _digest(source), "update_count": len(ordered),
            "latest_update": None if latest is None else {
                **{field: latest[field] for field in ("created", "modified", "when", "status")},
                "digest": latest_digest},
            "narrative_excerpt": _excerpt(latest["text"] if latest else description),
            **_LABELS, "canonical_record_id": None}


def parse_feed(raw):
    """Normalize a bounded feed; identical incident duplicates collapse by ID."""
    try:
        if type(raw) is not bytes or len(raw) > MAX_FEED_BYTES:
            _fail()
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                          parse_int=_integer, parse_float=_float,
                          parse_constant=lambda _: _fail())
        _guard(data)
        _source_tree(data)
        if not isinstance(data, list) or len(data) > MAX_STAGED_RECORDS:
            _fail()
        by_id = {}
        for item in data:
            candidate = _normalize(item)
            existing = by_id.get(candidate["id"])
            if existing is not None and existing != candidate:
                _fail()
            by_id[candidate["id"]] = candidate
        return sorted(by_id.values(), key=lambda row: row["id"])
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError, OverflowError):
        _fail()


def validate_staging(value):
    """Reject nonpending, malformed or oversized persisted staging envelopes."""
    try:
        _guard(value)
        _serialized(value)
        if (not isinstance(value, dict) or set(value) != {"schema_version", "source_url", "records"}
                or type(value["schema_version"]) is not int or value["schema_version"] != 1
                or value["source_url"] != FEED_URL
                or not isinstance(value["records"], list) or len(value["records"]) > MAX_STAGED_RECORDS):
            _fail()
        seen = []
        for row in value["records"]:
            if not isinstance(row, dict) or set(row) != _RECORD_FIELDS:
                _fail()
            identity = _text(row["id"], 128)
            if (not _ID.fullmatch(identity) or identity in seen
                    or row["source_url"] != "https://status.cloud.google.com/incidents/" + identity
                    or any(row[key] != label for key, label in _LABELS.items())):
                _fail()
            seen.append(identity)
            for field in ("begin", "created", "modified", "revision_at"):
                if _timestamp(row[field]) != row[field]:
                    _fail()
            if row["end"] is not None and (_timestamp(row["end"]) != row["end"]
                    or _time_key(row["end"]) < _time_key(row["begin"])):
                _fail()
            _text(row["description"], 4000, multiline=True)
            for field in ("affected_products", "currently_affected_locations", "previously_affected_locations"):
                if (any(not isinstance(item, dict) or set(item) != {"id", "title"} for item in row[field])
                        or _identities(row[field], allow_empty=field != "affected_products") != row[field]):
                    _fail()
            _optional_text(row["source_severity"], 100)
            _optional_text(row["status_impact"], 100)
            if (not isinstance(row["source_revision"], str) or not _HASH.fullmatch(row["source_revision"])
                    or type(row["update_count"]) is not int or not 0 <= row["update_count"] <= MAX_UPDATES):
                _fail()
            latest = row["latest_update"]
            if row["update_count"] == 0:
                if latest is not None:
                    _fail()
            else:
                if not isinstance(latest, dict) or set(latest) != _LATEST_FIELDS:
                    _fail()
                for field in ("created", "modified", "when"):
                    if _timestamp(latest[field]) != latest[field]:
                        _fail()
                _text(latest["status"], 100)
                if not isinstance(latest["digest"], str) or not _HASH.fullmatch(latest["digest"]):
                    _fail()
            expected_revision = max([row["modified"], *([latest["modified"]] if latest else [])], key=_time_key)
            if row["revision_at"] != expected_revision:
                _fail()
            excerpt = _text(row["narrative_excerpt"], MAX_EXCERPT_CHARS, empty=True)
            if len(excerpt.split()) > MAX_EXCERPT_WORDS or " ".join(excerpt.split()) != excerpt:
                _fail()
            canonical = row["canonical_record_id"]
            if canonical is not None and (not isinstance(canonical, str) or len(canonical) > 160
                                           or not _PUBLIC_ID.fullmatch(canonical)):
                _fail()
        if seen != sorted(seen):
            _fail()
        return deepcopy(value)
    except (ValueError, TypeError, KeyError, RecursionError, OverflowError):
        _fail()


def stage_feed(raw, *, previous=None, public_records=None):
    """Merge pending candidates deterministically; older source edits cannot win."""
    candidates = parse_feed(raw)
    previous = ({"schema_version": 1, "source_url": FEED_URL, "records": []}
                if previous is None else validate_staging(previous))
    if public_records is None:
        public_records = []
    if not isinstance(public_records, list) or len(public_records) > 1000:
        _fail()
    _guard(public_records)
    canonical = {}
    for record in public_records:
        if not isinstance(record, dict):
            _fail()
        identity, url = record.get("id"), record.get("source_url")
        if (not isinstance(identity, str) or len(identity) > 160 or not _PUBLIC_ID.fullmatch(identity)
                or not isinstance(url, str) or len(url) > 500 or not url.startswith("https://")
                or url in canonical):
            _fail()
        canonical[url] = identity
    merged = {row["id"]: row for row in previous["records"]}
    for candidate in candidates:
        existing = merged.get(candidate["id"])
        if existing is None or _time_key(candidate["revision_at"]) >= _time_key(existing["revision_at"]):
            merged[candidate["id"]] = candidate
    for row in merged.values():
        row["canonical_record_id"] = canonical.get(row["source_url"])
    return validate_staging({"schema_version": 1, "source_url": FEED_URL,
                             "records": sorted(merged.values(), key=lambda row: row["id"])})
