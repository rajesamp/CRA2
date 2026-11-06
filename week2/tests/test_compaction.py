"""Replay, source integrity, and adversarial transition checks for P1."""

from copy import deepcopy

import pytest

from week2.compaction import initial_state, reduce_state
from week2.contracts import (
    ContractError, validate_semantic_context, validate_semantic_transition,
)
from week2.semantic_state import serialize_state, validate_state
from week2.tests.test_semantic_state import (
    HISTORICAL, SERVICE, advance, make_context, result_for,
)


def test_deterministic_replay_preserves_reference_history_and_terminal_state():
    serialized_runs = []
    for _ in range(2):
        context = make_context()
        state = initial_state(context)
        states = [serialize_state(state, context)]
        for index in range(len(context["action_plan"])):
            prior = deepcopy(state)
            event = result_for(context, index)
            context["action_results"].append(event)
            state = reduce_state(prior, event, context)
            assert reduce_state(prior, event, context) == state
            assert set(prior["evidence_ids"]) <= set(state["evidence_ids"])
            states.append(serialize_state(state, context))
        assert state["completed_action_ids"] == [row["id"] for row in context["action_plan"]]
        assert state["evidence_ids"] == sorted(row["id"] for row in context["evidence"])
        assert state["unresolved_question_ids"] == ["q-history"]
        assert state["next_action"] is None
        serialized_runs.append(states)
    assert serialized_runs[0] == serialized_runs[1]


def test_reduce_does_not_mutate_or_alias_inputs():
    context = make_context()
    prior = initial_state(context)
    event = result_for(context, 0)
    context["action_results"].append(event)
    saved = deepcopy((context, prior, event))
    candidate = reduce_state(prior, event, context)
    assert (context, prior, event) == saved
    candidate["evidence_ids"].clear()
    candidate["policy_refs"].append("made-up")
    assert (context, prior, event) == saved


def test_unrecorded_repeated_and_out_of_order_actions_fail_without_changing_state():
    context = make_context()
    state = initial_state(context)
    saved = deepcopy(state)
    with pytest.raises(ContractError):
        reduce_state(state, result_for(context, 0), context)
    assert state == saved
    state = advance(context, state, 0)
    saved = deepcopy(state)
    with pytest.raises(ContractError):
        reduce_state(state, context["action_results"][0], context)
    context["action_results"].append(result_for(context, 2))
    with pytest.raises(ContractError):
        reduce_state(state, context["action_results"][-1], context)
    assert state == saved


@pytest.mark.parametrize("field,value", [
    ("id", "unknown-action"), ("action", "deploy"), ("service", "auth-service"),
    ("status", "error"), ("status", "approved"),
    ("evidence_ids", ["made-up"]), ("unresolved_question_ids", ["made-up"]),
])
def test_invalid_recorded_actions_are_rejected(field, value):
    context = make_context()
    prior = initial_state(context)
    event = result_for(context, 0)
    event[field] = value
    context["action_results"].append(event)
    with pytest.raises(ContractError):
        reduce_state(prior, event, context)
    assert prior["completed_action_ids"] == []


def test_action_suggestion_cannot_differ_from_external_ledger():
    context = make_context()
    prior = initial_state(context)
    event = result_for(context, 0)
    context["action_results"].append(deepcopy(event))
    event["evidence_ids"] = []
    with pytest.raises(ContractError):
        reduce_state(prior, event, context)


@pytest.mark.parametrize("field", ["claims", "risk_level", "approved", "policy", "freeze_window", "health"])
def test_action_cannot_introduce_operational_claims_or_decisions(field):
    context = make_context()
    prior = initial_state(context)
    event = result_for(context, 0)
    event[field] = "current and confirmed"
    context["action_results"].append(event)
    with pytest.raises(ContractError):
        reduce_state(prior, event, context)


@pytest.mark.parametrize("mutation", ["digest", "source", "kind", "origin", "service", "missing", "duplicate"])
def test_existing_evidence_provenance_cannot_be_replaced(mutation):
    context = make_context()
    state = advance(context, initial_state(context), 0)
    if mutation == "digest":
        context["evidence"][0]["content_digest"] = "e" * 64
    elif mutation == "source":
        context["evidence"][0]["source_id"] = "another-source.md"
    elif mutation == "kind":
        context["evidence"][0]["kind"] = "synthetic_snapshot"
    elif mutation == "origin":
        context["evidence"][0]["origin"] = "check_system_health"
    elif mutation == "service":
        context["evidence"][0]["service"] = "auth-service"
    elif mutation == "missing":
        context["evidence"].pop(0)
    else:
        context["evidence"].append(deepcopy(context["evidence"][0]))
    with pytest.raises(ContractError):
        validate_state(state, context)


def test_existing_question_or_action_ledger_cannot_be_rewritten():
    context = make_context()
    state = initial_state(context)
    for index in range(4):
        state = advance(context, state, index)
    changed_question = deepcopy(context)
    changed_question["questions"][0]["content_digest"] = "e" * 64
    with pytest.raises(ContractError):
        validate_state(state, changed_question)
    changed_ledger = deepcopy(context)
    changed_ledger["action_results"][3]["unresolved_question_ids"] = []
    with pytest.raises(ContractError):
        validate_state(state, changed_ledger)


def test_new_unreferenced_evidence_does_not_invalidate_existing_prefix():
    context = make_context()
    state = advance(context, initial_state(context), 0)
    context["evidence"].append({
        **context["evidence"][0], "id": "pm-cx102:chunk-1", "content_digest": "e" * 64,
    })
    assert validate_state(state, context) == state


@pytest.mark.parametrize("mutation", ["missing_key", "wrong_origin", "current_source", "confirmed_freeze"])
def test_tool_evidence_keeps_exact_synthetic_provenance(mutation):
    context = make_context()
    state = advance(context, initial_state(context), 0)
    event = result_for(context, 1)
    if mutation == "missing_key":
        event["evidence_ids"].pop()
    elif mutation == "wrong_origin":
        context["evidence"][1]["origin"] = "retrieve"
    elif mutation == "current_source":
        context["evidence"][1]["kind"] = "live"
    else:
        context["evidence"][1]["confirmed_freeze"] = True
    context["action_results"].append(event)
    with pytest.raises(ContractError):
        reduce_state(state, event, context)


def test_assessment_cannot_cite_uncollected_or_only_synthetic_evidence():
    for refs in ([HISTORICAL], [f"catalog:{SERVICE}.status"]):
        context = make_context()
        context["action_plan"] = [{"id": "a-assess", "action": "assess"}]
        state = initial_state(context)
        event = {"id": "a-assess", "action": "assess", "service": SERVICE,
                 "status": "ok", "evidence_ids": refs, "unresolved_question_ids": []}
        context["action_results"] = [event]
        with pytest.raises(ContractError):
            reduce_state(state, event, context)


def test_transition_cannot_skip_forward_or_revert_completed_work():
    context = make_context()
    first = initial_state(context)
    second = advance(context, first, 0)
    third = advance(context, second, 1)
    with pytest.raises(ContractError):
        validate_semantic_transition(first, third, context)
    with pytest.raises(ContractError):
        validate_semantic_transition(second, first, context)


def test_action_budget_is_bounded_before_any_transition():
    context = make_context()
    context["action_plan"] = [{"id": f"a-{index}", "action": "retrieve"} for index in range(33)]
    with pytest.raises(ContractError):
        validate_semantic_context(context)


def test_execution_cannot_reduce_stale_state_against_an_already_advanced_ledger():
    context = make_context()
    original = initial_state(context)
    first = advance(context, original, 0)
    advance(context, first, 1)
    # Historical projections remain independently inspectable for audit.
    assert validate_state(original, context) == original
    assert validate_state(first, context) == first
    with pytest.raises(ContractError):
        reduce_state(original, context["action_results"][0], context)
    with pytest.raises(ContractError):
        validate_semantic_transition(original, first, context)


def test_reducer_rejects_reference_overflow_instead_of_forgetting_old_evidence():
    context = make_context()
    context["evidence"] = [
        {**context["evidence"][0], "id": f"incident-{index}:chunk-1"}
        for index in range(65)
    ]
    context["action_plan"] = [{"id": "a-retrieve", "action": "retrieve"}]
    # The authority registry itself is bounded, so failure occurs before projection.
    with pytest.raises(ContractError):
        initial_state(context)


def test_tool_evidence_helper_preserves_identity_and_digest_of_validated_snapshot():
    from week2.contracts import semantic_tool_evidence
    from week2.semantic_state import digest
    from week2.tools import check_system_health

    raw = check_system_health(SERVICE)
    before = deepcopy(raw)
    records = semantic_tool_evidence("check_system_health", SERVICE, raw)
    assert raw == before
    assert [row["id"] for row in records] == sorted(raw["evidence"])
    assert {row["content_digest"] for row in records} == {digest(raw)}
    assert all(row["service"] == SERVICE and row["origin"] == "check_system_health"
               and row["kind"] == "synthetic_snapshot"
               and row["source_id"] == "data/checkout_system.json" for row in records)


@pytest.mark.parametrize("mutation", ["freeze", "active_incidents", "freshness", "service", "error", "credential"])
def test_tool_evidence_helper_rejects_fact_promotion_errors_and_credentials(mutation, monkeypatch):
    from secrets import token_hex
    from week2.contracts import semantic_tool_evidence
    from week2.tools import check_system_health

    secret = token_hex(24)
    monkeypatch.setenv("GROQ_API_KEY", secret)
    raw = check_system_health(SERVICE)
    if mutation == "freeze":
        raw["freeze_window"]["status"] = "confirmed"
    elif mutation == "active_incidents":
        raw["active_incidents"] = []
    elif mutation == "freshness":
        raw["source"]["freshness"] = "current"
    elif mutation == "service":
        raw["service_name"] = "auth-service"
    elif mutation == "error":
        raw = {"status": "error", "error": {"code": "source_unavailable"}}
    else:
        raw["source"]["path"] = secret
    with pytest.raises(ContractError) as failure:
        semantic_tool_evidence("check_system_health", SERVICE, raw)
    assert secret not in str(failure.value)


@pytest.mark.parametrize("reference", ["default:high_risk", "default:freeze_window_active"])
def test_default_policy_reference_cannot_masquerade_as_historical_evidence(reference):
    context = make_context()
    context["evidence"][0]["id"] = reference
    with pytest.raises(ContractError):
        validate_semantic_context(context)


def test_tool_evidence_pair_must_refer_to_one_snapshot_result():
    context = make_context()
    context["evidence"][1]["content_digest"] = "e" * 64
    context["action_results"] = [result_for(context, 0), result_for(context, 1)]
    with pytest.raises(ContractError):
        validate_semantic_context(context)
