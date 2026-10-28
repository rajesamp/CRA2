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
