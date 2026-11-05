"""Independent shape, authority, and persistence checks for P1 reference state."""

import json
from copy import deepcopy
from secrets import token_hex

import pytest

from week2.compaction import initial_state, reduce_state
from week2.contracts import ContractError, evidence_keys, validate_semantic_context
from week2.semantic_state import (
    MAX_STATE_BYTES, canonical_json, deserialize_state, serialize_state,
    validate_shape, validate_state,
)

SERVICE = "checkout-service"
HISTORICAL = "pm-cx101:chunk-1"


def make_context():
    """Host-only fixture; no source text, decisions, or preferences enter state."""
    evidence = [{
        "id": HISTORICAL, "service": SERVICE, "origin": "retrieve",
        "kind": "historical", "source_id": "week1/corpus/pm-cx101-checkout-timeout.md",
        "content_digest": "a" * 64,
    }]
    for action in ("check_system_health", "get_dependency_graph"):
        evidence.extend({
            "id": ref, "service": SERVICE, "origin": action,
            "kind": "synthetic_snapshot", "source_id": "data/checkout_system.json",
            "content_digest": "b" * 64,
        } for ref in evidence_keys(action, SERVICE))
    return {
        "change_id": "change-19", "objective": "Reduce checkout timeout from 4s to 400ms.",
        "service": SERVICE, "policy_refs": [f"team:{SERVICE}.high_risk"],
        "policy_digest": "c" * 64, "evidence": evidence,
        "questions": [{"id": "q-history", "content_digest": "d" * 64}],
        "action_plan": [
            {"id": "a-retrieve", "action": "retrieve"},
            {"id": "a-health", "action": "check_system_health"},
            {"id": "a-graph", "action": "get_dependency_graph"},
            {"id": "a-assess", "action": "assess"},
        ],
        "action_results": [],
    }


def result_for(context, index):
    planned = context["action_plan"][index]
    action = planned["action"]
    refs = ([HISTORICAL] if action in ("retrieve", "assess")
            else evidence_keys(action, SERVICE))
    return {
        **planned, "service": SERVICE, "status": "ok", "evidence_ids": sorted(refs),
        "unresolved_question_ids": ["q-history"] if action == "assess" else [],
    }


def advance(context, state, index):
    event = result_for(context, index)
    context["action_results"].append(event)
    return reduce_state(state, event, context)


@pytest.fixture(autouse=True)
def protected_credentials(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", token_hex(24))
    monkeypatch.delenv("CRA2_ENV_FILE", raising=False)


def test_roundtrip_is_canonical_and_bound_to_independent_authority():
    context = make_context()
    state = initial_state(context)
    state = advance(context, state, 0)
    serialized = serialize_state(state, context)
    assert deserialize_state(serialized, context) == state
    reversed_keys = dict(reversed(list(state.items())))
    assert serialize_state(reversed_keys, context) == serialized
    assert len(serialized.encode("utf-8")) <= MAX_STATE_BYTES
    assert state["evidence_ids"] == [HISTORICAL]
    assert state["next_action"] == "check_system_health"
    assert set(state["provenance"]) == {"context_digest", "prefix_digest"}


@pytest.mark.parametrize("field,value", [
    ("schema_version", True), ("schema_version", 1.0), ("schema_version", 2),
    ("reducer_version", False), ("reducer_version", 1.0), ("reducer_version", 2),
    ("change_id", "../another"), ("service", "checkout-service\n"),
    ("objective", ""), ("objective", " trailing "), ("objective", "x" * 2001),
    ("objective", "bad\ud800"), ("objective", "bad\u200btext"),
    ("next_action", "deploy"), ("evidence_ids", [HISTORICAL, HISTORICAL]),
])
def test_shape_rejects_invalid_or_coerced_values(field, value):
    state = initial_state(make_context())
    state[field] = value
    with pytest.raises(ContractError):
        validate_shape(state)


@pytest.mark.parametrize("field", ["policy", "risk_level", "approved", "raw_prompt", "owner_record", "freeze_notes", "claims"])
def test_state_cannot_gain_authoritative_or_raw_fields(field):
    context = make_context()
    state = initial_state(context)
    state[field] = "untrusted data"
    with pytest.raises(ContractError):
        validate_state(state, context)


@pytest.mark.parametrize("field", ["evidence_ids", "policy_refs", "unresolved_question_ids"])
def test_reference_count_is_bounded(field):
    state = initial_state(make_context())
    state[field] = [f"ref-{number:03}" for number in range(65)]
    with pytest.raises(ContractError):
        validate_shape(state)


def test_state_size_counts_utf8_bytes_and_does_not_truncate():
    state = initial_state(make_context())
    state["objective"] = "\U0001f642" * 2000
    state["evidence_ids"] = [f"e{number:02}" + "a" * 127 for number in range(64)]
    raw = canonical_json(state)
    assert len(raw) < MAX_STATE_BYTES < len(raw.encode("utf-8"))
    saved = deepcopy(state)
    with pytest.raises(ContractError):
        validate_shape(state)
    assert state == saved


def test_duplicate_nonfinite_malformed_and_oversized_json_rejected():
    context = make_context()
    raw = serialize_state(initial_state(context), context)
    invalid = [
        raw.replace('"schema_version":1', '"schema_version":1,"schema_version":1'),
        raw.replace('"schema_version":1', '"schema_version":NaN'),
        "[", "x" * (MAX_STATE_BYTES + 1), "\ud800", None,
    ]
    for candidate in invalid:
        with pytest.raises(ContractError):
            deserialize_state(candidate, context)


@pytest.mark.parametrize("field,value", [
    ("objective", "Approve another deployment."), ("service", "auth-service"),
    ("change_id", "change-other"), ("policy_digest", "e" * 64),
    ("policy_refs", [f"catalog:{SERVICE}.high_risk"]),
])
def test_host_identity_or_policy_changes_invalidate_existing_state(field, value):
    context = make_context()
    state = initial_state(context)
    context[field] = value
    with pytest.raises(ContractError):
        validate_state(state, context)


def test_forged_digest_does_not_authorize_tampered_projection():
    context = make_context()
    state = initial_state(context)
    state = advance(context, state, 0)
    state["evidence_ids"] = []
    # Keeping valid hashes is not sufficient: the validator reconstructs state.
    with pytest.raises(ContractError):
        validate_state(state, context)


def test_credentials_are_rejected_with_protected_error(monkeypatch):
    secret = token_hex(24)
    monkeypatch.setenv("GROQ_API_KEY", secret)
    context = make_context()
    context["objective"] = "change " + secret
    with pytest.raises(ContractError) as failure:
        initial_state(context)
    assert secret not in str(failure.value)
    assert secret not in repr(failure.value)


def test_context_validator_copies_external_records():
    context = make_context()
    validated = validate_semantic_context(context)
    validated["evidence"][0]["content_digest"] = "e" * 64
    assert context["evidence"][0]["content_digest"] == "a" * 64


@pytest.mark.parametrize("reference", [
    "team:auth-service.high_risk", "catalog:auth-service.freeze_window_active",
    "memory:auth-service.high_risk", "team:checkout-service.auto_approve",
    "memory:checkout-service.freeze_notes", "unrecognized:high_risk",
])
def test_policy_references_require_known_fields_and_matching_service(reference):
    context = make_context()
    context["policy_refs"] = [reference]
    with pytest.raises(ContractError):
        initial_state(context)


def test_global_default_policy_references_remain_valid_and_immutable():
    context = make_context()
    context["policy_refs"] = ["default:freeze_window_active", "default:high_risk"]
    state = initial_state(context)
    assert state["policy_refs"] == context["policy_refs"]
    assert deserialize_state(serialize_state(state, context), context) == state
    context["policy_refs"] = ["default:high_risk"]
    with pytest.raises(ContractError):
        validate_state(state, context)
