"""Reviewed, closed two-tool MCP contract; never trust a server's own baseline."""

import json
from copy import deepcopy

from jsonschema import Draft202012Validator

from week1.responses import guard

NAMES = ("check_system_health", "get_dependency_graph")
MAX_JSON = 65536
ERROR_CODES = (
    "invalid_input", "unknown_service", "source_unavailable", "invalid_source",
    "credential_rejected", "tool_unavailable",
)
NAME = {"type": "string", "minLength": 1, "maxLength": 200,
        "pattern": r"^[a-z0-9][a-z0-9-]*$", "not": {"pattern": r"[^a-z0-9-]"}}


class ContractError(ValueError):
    """Protected boundary error; the code contains no received data."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def obj(properties):
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


INPUT = obj({"service_name": NAME})
SOURCE = obj({
    "path": {"const": "data/checkout_system.json"},
    "kind": {"const": "synthetic_snapshot"},
    "observed_at": {"type": "null"}, "freshness": {"const": "unknown"},
})
ERROR = obj({"status": {"const": "error"},
             "error": obj({"code": {"enum": list(ERROR_CODES)}})})
LIST = {"type": "array", "items": NAME, "uniqueItems": True, "maxItems": 2000}
DIRECTION = obj({"direct": LIST, "transitive": LIST})
FIELDS = {
    NAMES[0]: {
        "health": {"enum": ["Healthy", "Degraded"]},
        "active_incidents": {"type": "null"},
        "active_incidents_status": {"const": "unknown"},
        "freeze_window": obj({"reported_active": {"type": "boolean"},
                              "status": {"enum": ["unconfirmed", "not_reported"]}}),
    },
    NAMES[1]: {"dependents": DIRECTION, "dependencies": DIRECTION},
}
DESCRIPTIONS = {
    NAMES[0]: "Read recorded health and freeze fields from a synthetic snapshot; freshness and active incidents are unknown.",
    NAMES[1]: "Read direct and transitive dependencies and dependents from a synthetic snapshot; freshness is unknown.",
}


def evidence_keys(name, service):
    if name == NAMES[0]:
        return [f"catalog:{service}.status", f"catalog:{service}.freeze_window_active"]
    return [f"graph:{service}.dependents", f"graph:{service}.dependencies"]


def descriptor(name):
    success = obj({"status": {"const": "ok"}, "service_name": NAME,
                   **FIELDS[name], "source": SOURCE,
                   "evidence": {"type": "array", "items": {"type": "string"},
                                "minItems": 2, "maxItems": 2, "uniqueItems": True}})
    return deepcopy({"name": name, "description": DESCRIPTIONS[name],
                     "inputSchema": INPUT,
                     "outputSchema": {"type": "object", "anyOf": [success, ERROR]}})


def checked(value, code):
    try:
        guard(value)
        raw = json.dumps(value, sort_keys=True, allow_nan=False)
        if len(raw.encode("utf-8")) > MAX_JSON:
            raise ValueError
    except (ValueError, TypeError, RecursionError):
        raise ContractError(code) from None
    return value


def validate_inventory(descriptors):
    checked(descriptors, "metadata_rejected")
    if not isinstance(descriptors, list) or len(descriptors) != 2:
        raise ContractError("metadata_rejected")
    expected = {name: descriptor(name) for name in NAMES}
    seen = set()
    for item in descriptors:
        name = item.get("name") if isinstance(item, dict) else None
        if (not isinstance(name, str) or name in seen or name not in expected
                or json.dumps(item, sort_keys=True) != json.dumps(expected[name], sort_keys=True)):
            raise ContractError("metadata_rejected")
        seen.add(name)
    return descriptors


def validate_arguments(name, arguments):
    checked(arguments, "invalid_input")
    if name not in NAMES or not Draft202012Validator(INPUT).is_valid(arguments):
        raise ContractError("invalid_input")
    return arguments


def validate_result(name, service, result):
    checked(result, "invalid_result")
    if name not in NAMES or not Draft202012Validator(
        descriptor(name)["outputSchema"]
    ).is_valid(result):
        raise ContractError("invalid_result")
    if result["status"] == "error":
        return result
    if (result["service_name"] != service
            or result["evidence"] != evidence_keys(name, service)):
        raise ContractError("invalid_result")
    if name == NAMES[0]:
        freeze = result["freeze_window"]
        expected = "unconfirmed" if freeze["reported_active"] else "not_reported"
        if freeze["status"] != expected:
            raise ContractError("invalid_result")
    else:
        for direction in ("dependents", "dependencies"):
            data = result[direction]
            if (any(items != sorted(items) or service in items for items in data.values())
                    or not set(data["direct"]) <= set(data["transitive"])):
                raise ContractError("invalid_result")
    return result


def decode_json(raw):
    def unique(pairs):
        data = {}
        for key, value in pairs:
            if key in data:
                raise ValueError
            data[key] = value
        return data

    try:
        if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_JSON:
            raise ValueError
        return json.loads(raw, object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, TypeError, RecursionError):
        raise ContractError("invalid_result") from None


def validate_semantic_context(context):
    """Validate the host-owned authority, never a model-editable state payload.

    Source digests and accepted results must originate in independent host
    validation. This checks consistency, not authenticity of caller-owned data.
    Raw evidence, policies and full audit records remain outside compact state.
    """
    from week2.semantic_state import (
        ACTIONS, DIGEST, IDENTIFIER, EVIDENCE_IDENTIFIER, MAX_ACTIONS, canonical_json, references,
    )
    record = obj({
        "id": EVIDENCE_IDENTIFIER, "service": NAME,
        "origin": {"enum": list(ACTIONS[:-1])},
        "kind": {"enum": ["historical", "external_public", "synthetic_snapshot"]},
        "source_id": {"type": "string", "minLength": 1, "maxLength": 500}, "content_digest": DIGEST,
    })
    # Local records retain their original P1/P2 scope rules. Public evidence has
    # a required human-readable company/service label, never a catalog alias.
    record["properties"]["source_service"] = {"anyOf": [
        {"type": "string", "minLength": 1, "maxLength": 200}, {"type": "null"},
    ]}
    plan_item = obj({"id": IDENTIFIER, "action": {"enum": list(ACTIONS)}})
    result = obj({
        "id": IDENTIFIER, "action": {"enum": list(ACTIONS)}, "service": NAME,
        "status": {"enum": ["ok", "error"]},
        "evidence_ids": references(evidence=True), "unresolved_question_ids": references(),
    })
    schema = obj({
        "change_id": IDENTIFIER,
        "objective": {"type": "string", "minLength": 1, "maxLength": 2000},
        "service": NAME, "policy_refs": references(), "policy_digest": DIGEST,
        "evidence": {"type": "array", "items": record, "maxItems": 64},
        "questions": {"type": "array", "maxItems": 64,
                      "items": obj({"id": IDENTIFIER, "content_digest": DIGEST})},
        "action_plan": {"type": "array", "items": plan_item, "minItems": 1, "maxItems": MAX_ACTIONS},
        "action_results": {"type": "array", "items": result, "maxItems": MAX_ACTIONS},
    })
    try:
        canonical_json(context)
        if not Draft202012Validator(schema).is_valid(context):
            raise ValueError
        from cra2.advisor import CATALOG
        from cra2.team_settings import SETTING_FIELDS
        if (context["service"] not in CATALOG
                or not context["objective"].strip()
                or context["objective"] != context["objective"].strip()
                or not context["policy_refs"]
                or context["policy_refs"] != sorted(context["policy_refs"])):
            raise ValueError
        allowed_policy_refs = {
            f"{origin}:{context['service']}.{field}"
            for origin in ("catalog", "team") for field in SETTING_FIELDS
        } | {f"default:{field}" for field in SETTING_FIELDS} | {
            f"change:settings.{field}" for field in SETTING_FIELDS
        } | {f"memory:{context['service']}.high_risk"}
        if not set(context["policy_refs"]) <= allowed_policy_refs:
            raise ValueError
        for key in ("evidence", "questions", "action_plan"):
            ids = [item["id"] for item in context[key]]
            if len(ids) != len(set(ids)):
                raise ValueError
        evidence = {item["id"]: item for item in context["evidence"]}
        questions = {item["id"] for item in context["questions"]}
        for item in evidence.values():
            if item["service"] != context["service"]:
                raise ValueError
            if item["kind"] == "external_public":
                source_service = item.get("source_service")
                if (not isinstance(source_service, str) or not source_service.strip()
                        or source_service != source_service.strip()
                        or source_service.casefold() in {name.casefold() for name in CATALOG}
                        or not item["id"].startswith("public-")
                        or not item["source_id"].startswith("https://")):
                    raise ValueError
            elif (item.get("source_service", context["service"]) not in (None, context["service"])
                  or item["id"].startswith("public-")):
                raise ValueError
            if item["origin"] == "retrieve":
                if item["kind"] not in ("historical", "external_public"):
                    raise ValueError
                # Reserved tool/policy namespaces cannot masquerade as history.
                if (item["id"].startswith(("catalog:", "graph:", "team:", "memory:", "change:", "default:"))
                        or item["id"] in context["policy_refs"]):
                    raise ValueError
            elif (item["kind"] != "synthetic_snapshot"
                  or item["source_id"] != "data/checkout_system.json"
                  or item["id"] not in evidence_keys(item["origin"], context["service"])):
                raise ValueError
        seen = set()
        if len(context["action_results"]) > len(context["action_plan"]):
            raise ValueError
        for index, action in enumerate(context["action_results"]):
            planned = context["action_plan"][index]
            if (action["id"] != planned["id"] or action["action"] != planned["action"]
                    or action["service"] != context["service"]):
                raise ValueError
            if action["status"] != "ok":
                raise ContractError("semantic_action_failed")
            refs = action["evidence_ids"]
            pending = action["unresolved_question_ids"]
            if (refs != sorted(refs) or pending != sorted(pending)
                    or not set(refs) <= evidence.keys() or not set(pending) <= questions):
                raise ValueError
            if action["action"] == "assess":
                # This records a validated assessment action, never its decision.
                if not set(refs) <= seen or not any(
                    evidence[ref]["kind"] in ("historical", "external_public") for ref in refs
                ):
                    raise ValueError
            else:
                if any(evidence[ref]["origin"] != action["action"] for ref in refs):
                    raise ValueError
                if action["action"] in NAMES and refs != sorted(evidence_keys(action["action"], context["service"])):
                    raise ValueError
                if action["action"] in NAMES and len({evidence[ref]["content_digest"] for ref in refs}) != 1:
                    raise ValueError
            seen.update(refs)
    except ContractError as exc:
        if exc.code == "semantic_action_failed":
            raise
        raise ContractError("invalid_semantic_context") from None
    except (ValueError, TypeError, KeyError, RecursionError, UnicodeError):
        raise ContractError("invalid_semantic_context") from None
    return deepcopy(context)


def validate_semantic_state(state, context):
    """Recompute the referenced prefix; compact state cannot rewrite authority."""
    from week2.compaction import _project
    from week2.semantic_state import canonical_json, validate_shape
    authority = validate_semantic_context(context)
    candidate = validate_shape(state)
    count = len(candidate["completed_action_ids"])
    if (count > len(authority["action_results"])
            or canonical_json(candidate) != canonical_json(_project(authority, count))):
        raise ContractError("semantic_state_conflict")
    return candidate


def validate_semantic_transition(previous, candidate, context):
    prior = validate_semantic_state(previous, context)
    next_state = validate_semantic_state(candidate, context)
    if (len(next_state["completed_action_ids"]) != len(prior["completed_action_ids"]) + 1
            or len(next_state["completed_action_ids"]) != len(context["action_results"])):
        raise ContractError("invalid_semantic_transition")
    return next_state


def semantic_tool_evidence(name, service, result):
    """Build source records only from the existing closed MCP result contract."""
    from week2.semantic_state import digest
    validated = validate_result(name, service, result)
    if validated["status"] != "ok":
        raise ContractError("semantic_action_failed")
    return [{"id": ref, "service": service, "origin": name,
             "kind": validated["source"]["kind"], "source_id": validated["source"]["path"],
             "content_digest": digest(validated)} for ref in sorted(validated["evidence"])]
