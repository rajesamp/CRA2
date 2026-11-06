"""New Google analogues retain their limits when tool execution resumes."""

from copy import deepcopy
from secrets import token_hex

import anyio
import pytest

from cra2.public_evidence import load_public_evidence, public_documents
from week2 import tools
from week2.compaction import initial_state, reduce_state
from week2.context_builder import build_context
from week2.contracts import NAMES, semantic_tool_evidence
from week2.execution import ActionExecution, ExecutionOptions, projected_review
from week2.execution import retrieval_records
from week2.preferences import effective_policy
from week2.semantic_state import deserialize_state, digest, serialize_state


GOOGLE_IDS = (
    "public-google-vertex-2026-02-27",
    "public-google-gcve-2026-07-14",
    "public-google-network-2026-08-20",
    "public-google-router-2026-09-01",
    "public-google-storage-2026-10-08",
    "public-google-power-2026-10-20",
)
SERVICE = "checkout-service"


@pytest.fixture(autouse=True)
def protected_environment(monkeypatch):
    monkeypatch.delenv("CRA2_ENV_FILE", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", token_hex(24))


def restore_and_replay(execution):
    """Resume from serialized state and independently replay host observations."""
    serialized = serialize_state(execution.state, execution.authority)
    execution.state = deserialize_state(serialized, execution.authority)
    assert serialize_state(execution.state, execution.authority) == serialized
    authority = deepcopy(execution.authority)
    observations, authority["action_results"] = authority["action_results"], []
    replayed = initial_state(authority)
    for observation in observations:
        authority["action_results"].append(observation)
        previous = deepcopy(replayed)
        replayed = reduce_state(previous, observation, authority)
        assert reduce_state(previous, observation, authority) == replayed
    assert execution.state == replayed


@pytest.mark.parametrize("mode", ["full", "threshold", "sac"])
@pytest.mark.parametrize("record_id", GOOGLE_IDS)
def test_google_analogue_survives_recovery_between_tools(mode, record_id):
    record = next(row for row in load_public_evidence() if row["id"] == record_id)
    document = next(row for row in public_documents() if row["doc_id"] == record_id)
    hit = {**document, "chunk_id": record_id + "#chunk-001", "score": 0.8}
    reference = hit["chunk_id"]
    execution = ActionExecution(
        "Review checkout dependency resilience and staged recovery.", SERVICE,
        effective_policy(SERVICE, None), ("retrieve", *NAMES, "assess"), mode=mode,
        options=ExecutionOptions(threshold_bytes=1),
    )
    records, store = retrieval_records([hit], SERVICE)
    execution.commit("retrieve", records, store)
    policy = deepcopy(execution.policy)
    expected_tools = {}

    def check_context(context):
        row = context["evidence"][reference]
        assert row["kind"] == "external_public"
        assert row["source_id"] == record["source_url"]
        assert row["source_service"] == record["original_service"] != SERVICE
        assert row["content"] == hit
        assert "Caveats: " + record["caveats"] in row["content"]["text"]
        assert "Reported facts: " + record["reported_facts"] in row["content"]["text"]
        assert record["prospective_cra2_risk"] is None
        assert "Prospective CRA2 risk: unassigned." in row["content"]["text"]
        assert context["policy"] == policy
        assert reference not in context["semantic_state"]["policy_refs"]
        if mode == "sac":
            assert "action_history" not in context
            assert context["compaction_count"] == len(execution.authority["action_results"])
        elif mode == "threshold":
            assert context["action_history"] == []
            assert context["compaction_count"] > 0
        else:
            assert context["action_history"] == execution.authority["action_results"]

    for name in NAMES:
        restore_and_replay(execution)

        async def tool_action(context, _charged):
            check_context(context)
            assert context["next_action"] == name
            assert execution.review_payload({"source_scope": "External analogues"}, context)[
                "tool_results"] == expected_tools
            return getattr(tools, name)(SERVICE)

        raw = anyio.run(execution.invoke, name, tool_action)
        expected_tools[name] = deepcopy(raw)
        records = semantic_tool_evidence(name, SERVICE, raw)
        execution.commit(name, records, {row["id"]: raw for row in records})

    restore_and_replay(execution)
    context = build_context(execution.state, execution.authority,
                            evidence_store=execution.evidence_store, policy=execution.policy,
                            mode=mode, threshold_bytes=1)
    check_context(context)
    assert context["next_action"] == "assess"
    payload = execution.review_payload({"source_scope": "External analogues"}, context)
    assert payload["documents"] == [hit]
    assert payload["incidents"] == []
    assert payload["tool_results"] == expected_tools
    assert all(raw["source"]["kind"] == "synthetic_snapshot"
               and reference not in raw["evidence"] for raw in expected_tools.values())
    comment = {"tag": "history", "severity": "low",
               "text": record["review_question_inferred"], "evidence": [reference]}
    review = projected_review({"out": {"comments": [comment]}, "tokens": [10, 5],
                               "cache_hit": False}, payload)
    assert review["out"]["comments"] == [comment]
    execution.commit("assess", evidence_ids=[reference], questions=[
        {"id": "google-review-question", "content_digest": digest(comment)},
    ])
    restore_and_replay(execution)
    assert execution.state["next_action"] is None
    assert execution.state["unresolved_question_ids"] == ["google-review-question"]
    assert reference in execution.state["evidence_ids"]
