"""Schema-driven, session-scoped change intake; no assessment or policy writes."""

import json
import unicodedata
from pathlib import Path

from cra2.advisor import CATALOG, RULES, clarification_questions
from week1.responses import guard

SCHEMA = Path(__file__).with_name("intake_schema.json")
KINDS = {"service": "service", "change_type": "change_type", "summary": "text",
         "change_window": "text", "deploy_plan": "text", "rollback_plan": "text",
         "monitoring_plan": "text"}
PLAN_LABELS = {"change_window": "Planned window", "deploy_plan": "Rollout plan",
               "rollback_plan": "Rollback plan", "monitoring_plan": "Monitoring plan"}
UNDEFINED = {"not yet defined", "not yet decided", "tbd", "unknown", "none"}


def load_schema(path=SCHEMA):
    """Only reviewed field identities and bounded prompt metadata are accepted."""
    raw = path.read_bytes()
    if len(raw) > 8192:
        raise ValueError("Invalid intake schema")
    data = json.loads(raw)
    if not isinstance(data, dict) or set(data) != {"version", "fields"} or type(data["version"]) is not int or data["version"] != 1:
        raise ValueError("Invalid intake schema")
    fields = data["fields"]
    if not isinstance(fields, list) or len(fields) != len(KINDS):
        raise ValueError("Invalid intake schema")
    seen = set()
    for field in fields:
        if not isinstance(field, dict) or set(field) != {"key", "question", "kind", "max_length"}:
            raise ValueError("Invalid intake schema")
        key = field["key"]
        if (not isinstance(key, str) or key not in KINDS or key in seen
                or field["kind"] != KINDS[key]
                or not isinstance(field["question"], str) or not 1 <= len(field["question"].strip()) <= 250
                or type(field["max_length"]) is not int or not 1 <= field["max_length"] <= 600):
            raise ValueError("Invalid intake schema")
        if key == "summary" and not {"service", "change_type"} <= seen:
            raise ValueError("Invalid intake schema order")
        seen.add(key)
    guard(fields)
    return fields


def choices(field):
    if field["kind"] == "service":
        return sorted(CATALOG)
    if field["kind"] == "change_type":
        return list(RULES["system1"]["change_type"])
    return []


def new_draft():
    return {"step": 0, "values": {}}


def _clean(value, field, values):
    if not isinstance(value, str) or not value.strip() or len(value) > field["max_length"]:
        raise ValueError("Enter a nonempty answer within the field limit.")
    if any(unicodedata.category(c).startswith("C") and c not in "\n\r\t" for c in value):
        raise ValueError("Remove invisible or control characters.")
    value = value.strip()
    guard(value)
    allowed = choices(field)
    if allowed and value not in allowed:
        raise ValueError("Choose one of the listed values.")
    if field["key"] == "summary":
        candidate = {**values, "summary": value}
        if clarification_questions(candidate):
            raise ValueError("Describe the affected component and concrete before/after change.")
    return value


def advance(draft, answer, fields):
    """Validate the current answer; failed updates leave the draft unchanged."""
    step = draft["step"]
    if not 0 <= step < len(fields):
        raise ValueError("The draft is complete. Go back to revise it.")
    field = fields[step]
    value = _clean(answer, field, draft["values"])
    return {"step": step + 1, "values": {**draft["values"], field["key"]: value}}


def previous(draft):
    return {"step": max(0, draft["step"] - 1), "values": dict(draft["values"])}


def open_items(draft):
    """Highlight explicitly unknown notes, without claiming readiness otherwise."""
    return [label for key, label in PLAN_LABELS.items()
            if draft["values"].get(key, "").strip().casefold().rstrip(".") in UNDEFINED]


def review_question(draft, fields):
    """Revalidate the packet, but hand off only service and change description.

    Plans/window are human-review notes, not verified policy or model evidence.
    The caller must submit the question through the original chat guard.
    """
    values = draft["values"]
    if draft["step"] != len(fields) or set(values) != set(KINDS):
        raise ValueError("Finish the intake before preparing a review.")
    for field in fields:
        _clean(values[field["key"]], field, values)
    question = f"Assess the risk of changing {values['service']}: {values['summary']}"
    guard(question)
    return question
