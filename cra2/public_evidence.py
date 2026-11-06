"""Validated public corporate analogues, separate from catalog incident history.

Source reports are concise curated paraphrases, not live health, local policy,
approval or prospective risk labels. Retrieval hits must match canonical data.
"""

import json
import math
import os
import re
import stat
import unicodedata
from copy import deepcopy
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlsplit

from cra2 import config
from cra2.incidents import _terms
from cra2.secrets import reject_credentials

SCHEMA_VERSION = 1
DATASET = "public_corporate"
MAX_FILE_BYTES = 1_048_576
MAX_DOCUMENT_WORDS = 500
KINDS = {"incident_report": "external_incident", "change_plan": "external_change_plan"}
_TOP = {"schema_version", "dataset_id", "created_on", "content_policy", "rights_status", "records"}
_FIELDS = {
    "id", "company", "incident_date", "planned_change_date", "record_type",
    "original_service", "source_url", "reported_facts", "reported_recovery",
    "risk_topics_inferred", "review_question_inferred", "caveats", "source_kind",
    "original_severity", "prospective_cra2_risk", "access_checked_on",
}
# This curated collection only accepts the first-party publishers reviewed for it.
_HOSTS = {
    "blog.cloudflare.com", "github.blog", "www.atlassian.com", "about.gitlab.com",
    "aws.amazon.com", "www.fastly.com", "engineering.fb.com", "slack.engineering",
    "status.cloud.google.com", "gitlab.com",
}
# Multiword change types and generic review language must not satisfy the
# cross-company relevance gate by themselves (e.g. 'configuration rollout').
_GENERIC_TERMS = _terms(
    "configuration config rollout release code infrastructure change review risk "
    "production staging test testing validation procedure requirement checklist "
    "control update software planned maintenance operation"
)


class PublicEvidenceError(ValueError):
    """Protected failure; never includes source content or credentials."""


def _fail():
    raise PublicEvidenceError("Invalid public corporate evidence") from None


def _guard(value):
    try:
        reject_credentials(value, additional=(os.getenv("CRA2_UI_USER"), os.getenv("CRA2_UI_PASSWORD")))
    except ValueError:
        _fail()


def _text(value, limit):
    if (not isinstance(value, str) or not value or value != value.strip()
            or len(value) > limit
            or any(unicodedata.category(char).startswith("C") for char in value)):
        _fail()


def _date(value):
    _text(value, 10)
    try:
        if date.fromisoformat(value).isoformat() != value:
            _fail()
    except ValueError:
        _fail()


def _url(value):
    _text(value, 500)
    try:
        if re.search(r"%(?![0-9A-Fa-f]{2})", value):
            _fail()
        parsed = urlsplit(value)
        decoded = unquote(value, errors="strict")
        _guard(decoded)
        if (not value.startswith("https://") or parsed.scheme != "https"
                or parsed.netloc not in _HOSTS or parsed.username or parsed.password
                or parsed.port is not None or not parsed.path.startswith("/")
                or parsed.query or parsed.fragment
                or any(char.isspace() or unicodedata.category(char).startswith("C")
                       for char in decoded)
                or any(char in decoded for char in "\\<>()%")
                or not value.isascii()):
            _fail()
    except ValueError:
        _fail()


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail()
        result[key] = value
    return result


def _read(path):
    """Bounded regular-file read; reject symlink files and selected directories."""
    path = Path(path)
    _guard(str(path))
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        _fail()
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                             | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(descriptor, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                _fail()
            raw = stream.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            _fail()
        result = json.loads(raw.decode("utf-8"), object_pairs_hook=_object,
                            parse_constant=lambda _value: _fail())
        _guard(result)
        return result
    except (OSError, UnicodeError, ValueError, RecursionError):
        _fail()


def _collection(data_dir=None):
    directory = config.DATA_DIR if data_dir is None else Path(data_dir)
    data = _read(directory / "public_evidence.json")
    catalog = _read(directory / "checkout_system.json")
    if (not isinstance(catalog, dict) or not isinstance(catalog.get("services"), dict)
            or not catalog["services"]
            or any(not isinstance(key, str) for key in catalog["services"])):
        _fail()
    local_services = {key.casefold() for key in catalog["services"]}
    if (not isinstance(data, dict) or set(data) != _TOP
            or type(data["schema_version"]) is not int or data["schema_version"] != SCHEMA_VERSION
            or data["dataset_id"] != "cra2-public-corporate-v1"):
        _fail()
    _date(data["created_on"])
    for field in ("content_policy", "rights_status"):
        _text(data[field], 1000)
    records = data["records"]
    if not isinstance(records, list) or not 1 <= len(records) <= 256:
        _fail()
    seen = set()
    seen_urls = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != _FIELDS:
            _fail()
        for field, limit in (
            ("id", 160), ("company", 100), ("original_service", 200),
            ("record_type", 30), ("reported_facts", 2000),
            ("review_question_inferred", 500), ("caveats", 1000),
            ("source_kind", 40),
        ):
            _text(record[field], limit)
        if (not re.fullmatch(r"public-[a-z0-9]+(?:-[a-z0-9]+)*", record["id"])
                or record["id"] in seen or record["record_type"] not in KINDS
                or record["source_kind"] != "first_party_corporate"
                or record["original_service"].casefold() in local_services
                or record["original_severity"] is not None
                or record["prospective_cra2_risk"] is not None):
            _fail()
        seen.add(record["id"])
        _url(record["source_url"])
        if record["source_url"] in seen_urls:
            _fail()
        seen_urls.add(record["source_url"])
        _date(record["access_checked_on"])
        if record["record_type"] == "incident_report":
            _date(record["incident_date"])
            if record["planned_change_date"] is not None:
                _fail()
            _text(record["reported_recovery"], 2000)
        else:
            _date(record["planned_change_date"])
            if record["incident_date"] is not None or record["reported_recovery"] is not None:
                _fail()
        topics = record["risk_topics_inferred"]
        if not isinstance(topics, list) or not 1 <= len(topics) <= 12:
            _fail()
        for topic in topics:
            _text(topic, 100)
        if len(set(topics)) != len(topics):
            _fail()
        if not record["review_question_inferred"].endswith("?"):
            _fail()
        _document(record, data)
    return data


def _document(record, collection):
    is_incident = record["record_type"] == "incident_report"
    event_date = record["incident_date"] if is_incident else record["planned_change_date"]
    title = f"{record['company']}: {'incident report' if is_incident else 'change plan'} ({event_date})"
    lines = [
        "# " + title,
        "External corporate analogue; not current health, local policy, approval or same-service history.",
        "Company: " + record["company"],
        "Original service: " + record["original_service"],
        "Source type: " + record["source_kind"],
        "Source: " + record["source_url"],
        ("Incident date: " if is_incident else "Planned change date: ") + event_date,
        "Access checked on: " + record["access_checked_on"],
        "Reported facts: " + record["reported_facts"],
        "Reported recovery: " + (record["reported_recovery"] or "Not applicable; change plan does not establish an outcome."),
        "CRA2-inferred topics (not company labels): " + ", ".join(record["risk_topics_inferred"]),
        "CRA2-inferred review question: " + record["review_question_inferred"],
        "Caveats: " + record["caveats"],
        "Original severity: not extracted in this curated record. Prospective CRA2 risk: unassigned.",
        "Rights: " + collection["rights_status"],
    ]
    text = "\n".join(lines)
    _guard(text)
    if len(text.split()) > MAX_DOCUMENT_WORDS or len(text.encode("utf-8")) > 16000:
        _fail()
    return {"doc_id": record["id"], "title": title, "source": record["source_url"],
            "kind": KINDS[record["record_type"]], "service": record["original_service"],
            "source_dataset": DATASET, "text": text}


def load_public_evidence(data_dir=None):
    """Load validated canonical records, preserving source identities and null labels."""
    return deepcopy(_collection(data_dir)["records"])


def public_documents(data_dir=None):
    """Each source remains one complete bounded retrieval document, never split."""
    collection = _collection(data_dir)
    return [_document(record, collection) for record in collection["records"]]


def match_terms_by_id(data_dir=None):
    """Analogue relevance excludes boilerplate, URLs and generated questions."""
    return {record["id"]: _terms(" ".join([
        record["reported_facts"], record["reported_recovery"] or "",
        *record["risk_topics_inferred"],
    ])) - _GENERIC_TERMS for record in load_public_evidence(data_dir)}


def validate_public_hit(hit, data_dir=None):
    """Reject forged provenance or source text; only the similarity score varies."""
    if not isinstance(hit, dict):
        _fail()
    _guard(hit)
    candidates = {document["doc_id"]: document for document in public_documents(data_dir)}
    doc_id = hit.get("doc_id")
    if not isinstance(doc_id, str) or doc_id not in candidates:
        _fail()
    document = candidates[doc_id]
    if (set(hit) != set(document) | {"chunk_id", "score"}
            or any(hit[key] != value for key, value in document.items())
            or hit["chunk_id"] != doc_id + "#chunk-001"
            or type(hit["score"]) not in (int, float)
            or not -1 <= hit["score"] <= 1 or not math.isfinite(hit["score"])):
        _fail()
    return deepcopy(hit)
