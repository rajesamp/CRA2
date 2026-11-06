"""P1 reference-only execution state. This is not a policy or an approval.

The host context and validated action ledger stay outside this representation.
All public loaders require that independent authority; a digest is not a signature.
"""

import hashlib
import json
import unicodedata
from copy import deepcopy

from jsonschema import Draft202012Validator

from week2.contracts import ContractError, checked, decode_json, obj

SCHEMA_VERSION = 1
REDUCER_VERSION = 1
MAX_STATE_BYTES = 16384
MAX_ACTIONS = 32
MAX_REFERENCES = 64
ACTIONS = ("retrieve", "check_system_health", "get_dependency_graph", "assess")
IDENTIFIER = {"type": "string", "minLength": 1, "maxLength": 200,
              "pattern": r"^[A-Za-z0-9][A-Za-z0-9_.:/-]*$"}
EVIDENCE_IDENTIFIER = dict(IDENTIFIER, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/#-]*$")
DIGEST = {"type": "string", "pattern": r"^[a-f0-9]{64}$", "maxLength": 64}


def references(limit=MAX_REFERENCES, *, evidence=False):
    return {"type": "array", "items": EVIDENCE_IDENTIFIER if evidence else IDENTIFIER,
            "uniqueItems": True, "maxItems": limit}


STATE_SCHEMA = obj({
    "schema_version": {"type": "integer", "const": SCHEMA_VERSION},
    "reducer_version": {"type": "integer", "const": REDUCER_VERSION},
    "change_id": IDENTIFIER,
    "objective": {"type": "string", "minLength": 1, "maxLength": 2000},
    "service": IDENTIFIER,
    "completed_action_ids": references(MAX_ACTIONS),
    "evidence_ids": references(evidence=True),
    "policy_refs": references(),
    "unresolved_question_ids": references(),
    "next_action": {"enum": [*ACTIONS, None]},
    "provenance": obj({"context_digest": DIGEST, "prefix_digest": DIGEST}),
})


def canonical_json(value):
    """Stable UTF-8 JSON; reject controls, invalid Unicode and non-JSON values."""
    try:
        checked(value, "invalid_semantic_state")
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False,
                         sort_keys=True, separators=(",", ":"))
        # Check decoded strings too: JSON escaping must not hide control data.
        def visit(item):
            if isinstance(item, str):
                if any(unicodedata.category(c).startswith("C") for c in item):
                    raise ValueError
            elif isinstance(item, dict):
                for key, val in item.items():
                    if not isinstance(key, str):
                        raise ValueError
                    visit(key)
                    visit(val)
            elif isinstance(item, list):
                for val in item:
                    visit(val)
            elif item is not None and type(item) not in (bool, int, float):
                raise ValueError
        visit(value)
        raw.encode("utf-8")
        return raw
    except (ValueError, TypeError, RecursionError, UnicodeError):
        raise ContractError("invalid_semantic_state") from None


def digest(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def validate_shape(state):
    raw = canonical_json(state)
    if (len(raw.encode("utf-8")) > MAX_STATE_BYTES
            or not Draft202012Validator(STATE_SCHEMA).is_valid(state)
            or type(state["schema_version"]) is not int
            or type(state["reducer_version"]) is not int
            or state["objective"] != state["objective"].strip()):
        raise ContractError("invalid_semantic_state")
    return deepcopy(state)


def validate_state(state, context):
    from week2.contracts import validate_semantic_state
    return validate_semantic_state(state, context)


def serialize_state(state, context):
    return canonical_json(validate_state(state, context))


def deserialize_state(raw, context):
    try:
        if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_STATE_BYTES:
            raise ValueError
        state = decode_json(raw)
    except (ValueError, TypeError, UnicodeError):
        raise ContractError("invalid_semantic_state") from None
    return validate_state(state, context)
