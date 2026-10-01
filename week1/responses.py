"""Validated response copy and exact FAQ aliases; no routing code in JSON."""

import json
import os
import re
import unicodedata
from pathlib import Path
from string import Formatter

from cra2.advisor import ADVISORY
from cra2.secrets import reject_credentials
from cra2.system2 import _DECISION

CATALOG_PATH = Path(__file__).with_name("responses.json")
_PARAMETERS = {
    "unknown_dataset_service": {"services"},
    "distinct_title_count": {"count"},
    "incident_count": {"count"},
    "specific_change": {"service"},
    "risk_indication": {"level"},
    "high_risk_policy": {"source"},
    "freeze_policy": {"source"},
    "capability_limit": {"total"},
}
_PLAIN = {
    "out_of_scope",
    "help",
    "input_length",
    "control_characters",
    "invalid_mode",
    "multiple_services",
    "no_scenarios",
    "advisory_boundary",
    "memory_deferred",
    "tools_deferred",
    "missing_service",
    "no_evidence",
    "history_comparison",
    "no_historical_evidence",
    "evidence_only",
    "no_model_evidence",
    "review_questions",
    "provider_unavailable",
    "evidence_heading",
    "guidance_prefix",
    "help_or_change",
    "browse_or_change",
    "missing_task",
    "dataset_service_filter",
    "dataset_fields",
    "title_or_fields",
    "count_or_list",
}


def guard(value):
    """Keep provider and optional UI-auth credentials out of application data."""
    reject_credentials(
        value, additional=(os.getenv("CRA2_UI_USER"), os.getenv("CRA2_UI_PASSWORD"))
    )


def clarify(text, *, scope=None):
    trace = {"status": "needs_clarification", "retrieved": []}
    if scope:
        trace["scope"] = scope
    return text + "\n\n" + ADVISORY, trace


def normalize_question(question):
    """Exact aliases ignore case, whitespace, and terminal sentence punctuation."""
    return " ".join(question.casefold().split()).rstrip(".?!").rstrip()


def _invalid():
    raise ValueError("Invalid Week 1 response catalog; check responses.json")


def _text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 4000:
        _invalid()
    if any(
        unicodedata.category(c).startswith("C") and c not in "\n\r\t" for c in value
    ):
        _invalid()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _invalid()
        result[key] = value
    return result


def load():
    """Read each request so JSON-only edits take effect without a restart.

    Broken catalogs fail before retrieval or a provider call. Error text never
    includes catalog values. The catalog is trusted, reviewed application copy,
    not a runtime write target for the conversational agent.
    """
    failed = False
    try:
        with CATALOG_PATH.open("rb") as source:
            raw = source.read(65537)
        if len(raw) > 65536:
            _invalid()
        data = json.loads(raw, object_pairs_hook=_unique_object)
        guard(data)
        if not isinstance(data, dict) or set(data) != {
            "version",
            "messages",
            "capabilities",
            "field_labels",
            "faq",
        }:
            _invalid()
        if type(data["version"]) is not int or data["version"] != 1:
            _invalid()
        messages = data["messages"]
        if not isinstance(messages, dict) or set(messages) != _PLAIN | set(_PARAMETERS):
            _invalid()
        for key, value in messages.items():
            _text(value)
            fields = set()
            for _, field, spec, conversion in Formatter().parse(value):
                if field is not None:
                    if spec or conversion or field not in _PARAMETERS.get(key, set()):
                        _invalid()
                    fields.add(field)
            if fields != _PARAMETERS.get(key, set()):
                _invalid()
        capabilities = data["capabilities"]
        if not isinstance(capabilities, list) or not 1 <= len(capabilities) <= 20:
            _invalid()
        for label in capabilities:
            _text(label)
        labels = data["field_labels"]
        if not isinstance(labels, dict) or set(labels) != {
            "incident_id",
            "service",
            "root_cause",
            "severity",
        }:
            _invalid()
        for label in labels.values():
            _text(label)
        if not isinstance(data["faq"], list) or len(data["faq"]) > 50:
            _invalid()
        ids, aliases = set(), set()
        for entry in data["faq"]:
            if not isinstance(entry, dict) or set(entry) != {
                "id",
                "questions",
                "answer",
            }:
                _invalid()
            if (
                not isinstance(entry["id"], str)
                or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", entry["id"])
                or entry["id"] in ids
            ):
                _invalid()
            ids.add(entry["id"])
            _text(entry["answer"])
            # Conservative output hygiene, not proof of factual correctness.
            if _DECISION.search(entry["answer"]) or re.search(
                r"\brisk\s+(?:score|indication)\s*:", entry["answer"], re.IGNORECASE
            ):
                _invalid()
            if (
                not isinstance(entry["questions"], list)
                or not 1 <= len(entry["questions"]) <= 20
            ):
                _invalid()
            for question in entry["questions"]:
                _text(question)
                alias = normalize_question(question)
                if not alias or alias in aliases:
                    _invalid()
                aliases.add(alias)
    except (OSError, ValueError, TypeError, RecursionError):
        failed = True
    if failed:
        _invalid()
    return data


def message(catalog, key, **values):
    return catalog["messages"][key].format(**values)


def faq(catalog, question):
    alias = normalize_question(question)
    return next(
        (
            entry
            for entry in catalog["faq"]
            if any(normalize_question(q) == alias for q in entry["questions"])
        ),
        None,
    )
