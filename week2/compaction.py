"""Pure deterministic projection of host-validated action records (P1 only).

No tool execution, LLM summaries, risk decisions, clocks, I/O or persistence.
The caller appends a validated result to the external ledger before reduction.
"""

from week2.contracts import (
    ContractError, validate_semantic_context, validate_semantic_state,
    validate_semantic_transition,
)
from week2.semantic_state import REDUCER_VERSION, SCHEMA_VERSION, digest, validate_shape


def _project(context, count):
    """Internal projection; callers validate the context and action prefix first."""
    actions = context["action_results"][:count]
    evidence = sorted({ref for action in actions for ref in action["evidence_ids"]})
    questions = sorted({ref for action in actions for ref in action["unresolved_question_ids"]})
    immutable = {key: context[key] for key in (
        "change_id", "objective", "service", "policy_refs", "policy_digest", "action_plan")}
    source_records = sorted((record for record in context["evidence"]
                             if record["id"] in evidence), key=lambda record: record["id"])
    question_records = sorted((record for record in context["questions"]
                               if record["id"] in questions), key=lambda record: record["id"])
    return validate_shape({
        "schema_version": SCHEMA_VERSION, "reducer_version": REDUCER_VERSION,
        "change_id": context["change_id"], "objective": context["objective"],
        "service": context["service"],
        "completed_action_ids": [action["id"] for action in actions],
        "evidence_ids": evidence, "policy_refs": sorted(context["policy_refs"]),
        "unresolved_question_ids": questions,
        "next_action": (context["action_plan"][count]["action"]
                        if count < len(context["action_plan"]) else None),
        "provenance": {"context_digest": digest(immutable),
                       "prefix_digest": digest({"actions": actions, "evidence": source_records,
                                                "questions": question_records})},
    })


def initial_state(context):
    """Create an empty execution state bound to host request/policy/plan identity."""
    return _project(validate_semantic_context(context), 0)


def reduce_state(previous, action_result, context):
    """Accept exactly the next independently recorded action, or raise safely.

    Overflow and failed actions leave the previous state untouched. Repeating an
    action against the same prior state is deterministic; applying it twice fails.
    """
    authority = validate_semantic_context(context)
    prior = validate_semantic_state(previous, authority)
    count = len(prior["completed_action_ids"])
    if count >= len(authority["action_results"]):
        raise ContractError("unrecorded_semantic_action")
    if len(authority["action_results"]) != count + 1:
        raise ContractError("stale_semantic_state")
    from week2.semantic_state import canonical_json
    if canonical_json(action_result) != canonical_json(authority["action_results"][count]):
        raise ContractError("semantic_action_conflict")
    candidate = _project(authority, count + 1)
    return validate_semantic_transition(prior, candidate, authority)
