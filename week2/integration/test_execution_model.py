"""Explicit P2 gate: verified real encoder, fresh index and actual MCP subprocesses.

Run separately from the clean-checkout offline suite. Missing/corrupt model
artifacts fail this gate; it never downloads, calls Groq, or contacts Slack.
"""

from copy import deepcopy
from pathlib import Path
import tempfile

import pytest

from cra2 import system2
from cra2.advisor import ADVISORY
from week1 import retrieval, setup_index
from week2 import execution, workflow
from week2.contracts import NAMES
from week2.execution import ExecutionOptions
from week2.memory import MemoryStore

SERVICE = "checkout-service"
CHANGE = (
    "Change checkout-service freeze-window logging flag from false to true. "
    "Verify authoritative time-stamped sources, stale snapshot claims, and "
    "unconfirmed freeze applicability."
)


@pytest.fixture(scope="module")
def real_index():
    directory = setup_index.provision_model(download=False)
    setup_index._validate_model(directory)
    retrieval._default_encoder.cache_clear()
    encoder = retrieval._default_encoder()
    assert retrieval._encoder_identity(encoder).startswith("fastembed-artifacts-sha256:")
    corpus = Path(__file__).resolve().parents[2] / "week1" / "corpus"
    with tempfile.TemporaryDirectory(prefix="cra2-p2-model-", dir="/tmp") as temporary:
        index = Path(temporary) / "real-corpus.sqlite3"
        counts = retrieval.build_index(corpus, index, encoder=encoder)
        assert counts["chunks"] >= counts["documents"] > 0
        expected = retrieval.search(CHANGE, index, encoder=encoder, limit=3, service=SERVICE)
        assert len(expected) == 3
        assert any(hit["service"] is None for hit in expected)
        assert any(hit["service"] == SERVICE for hit in expected)
        assert all("#chunk-" in hit["chunk_id"] for hit in expected)
        yield index, encoder, expected


def all_keys(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield key
            yield from all_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from all_keys(nested)


@pytest.mark.parametrize("context_mode", ["full", "threshold", "sac"])
@pytest.mark.parametrize("assessment_mode", ["Local evidence only", "Groq assessment"])
def test_real_sources_cross_each_experimental_action_boundary(
        real_index, monkeypatch, context_mode, assessment_mode):
    index, encoder, expected = real_index
    retrieved, contexts, requests = [], [], []

    def no_live(*_args, **_kwargs):
        pytest.fail("Real-source integration must not call a provider")

    monkeypatch.delenv("CRA2_ENV_FILE", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setattr(system2, "client", no_live)
    monkeypatch.setattr(system2, "_protected_client", no_live)

    original_builder = execution.build_context
    def capture_context(*args, **kwargs):
        context = original_builder(*args, **kwargs)
        contexts.append(deepcopy(context))
        return context
    monkeypatch.setattr(execution, "build_context", capture_context)

    def retrieve(query, _index, **options):
        hits = retrieval.search(query, index, encoder=encoder, **options)
        retrieved.append(deepcopy(hits))
        return hits

    def review(payload, _weights):
        assert assessment_mode == "Groq assessment"
        requests.append(deepcopy(payload))
        historical = payload["incidents"] + payload["documents"]
        return {"out": {"comments": [{"tag": "history", "severity": "low",
            "text": "Could independent verification check source freshness before reviewing this change?",
            "evidence": [historical[0]["chunk_id"]]}]},
            "cache_hit": False, "request_attempted": False, "tokens": None,
            "model": "offline-real-source-fixture"}

    with tempfile.TemporaryDirectory(prefix="cra2-p2-memory-", dir="/tmp") as temporary:
        memory = MemoryStore(Path(temporary) / "memory.sqlite3")
        memory.write(SERVICE, high_risk=True)
        # No tool_runner override: each selected action uses the actual default
        # stdio MCP client/server, reviewed inventory and result validation.
        answer, trace = workflow.respond(CHANGE, mode=assessment_mode,
            context_mode=context_mode, retriever=retrieve, reviewer=review,
            memory_store=memory, index_path=index,
            execution_options=ExecutionOptions(threshold_bytes=1))

    assessed = assessment_mode == "Groq assessment"
    expected_count = 4 if assessed else 3
    assert trace["status"] == ("assessed" if assessed else "evidence_only")
    assert trace["execution"]["status"] == "completed"
    assert trace["execution"]["mode"] == context_mode
    assert trace["execution"]["action_count"] == expected_count
    assert trace["execution"]["completed_actions"] == expected_count
    assert trace["execution"]["model_action_count"] == int(assessed)
    assert trace["execution"]["context_tokens"] is None
    assert trace["request_attempted"] is False
    assert answer.endswith(ADVISORY)
    assert len(retrieved) == 1 and retrieved[0] == expected
    assert len(contexts) == expected_count
    assert [context["next_action"] for context in contexts] == [
        "retrieve", *NAMES, *(["assess"] if assessed else [])]

    for index_number, context in enumerate(contexts):
        assert context["context_mode"] == context_mode
        assert context["service"] == SERVICE
        assert context["objective"] == CHANGE
        assert context["policy"]["effective"]["high_risk"] is True
        if context_mode == "sac":
            assert "action_history" not in context
        elif context_mode == "threshold":
            assert context["action_history"] == []
        else:
            assert len(context["action_history"]) == index_number
        if index_number:
            for hit in expected:
                source = context["evidence"][hit["chunk_id"]]
                assert source["content"] == hit
                assert source["source_id"] == hit["source"]
                assert source["source_service"] == hit["service"]
                assert source["kind"] == "historical"

    events = trace["events"]
    assert [event["tool"] for event in events] == list(NAMES)
    for event in events:
        assert event["input"] == {"service_name": SERVICE}
        assert event["output"]["source"] == {
            "path": "data/checkout_system.json", "kind": "synthetic_snapshot",
            "observed_at": None, "freshness": "unknown"}
    health = events[0]["output"]
    assert health["active_incidents"] is None
    assert health["active_incidents_status"] == "unknown"
    assert health["freeze_window"]["status"] in {"unconfirmed", "not_reported"}
    assert "current production state" in answer
    assert not ({"semantic_state", "authority", "evidence_store", "action_history",
                 "current_observation", "execution_context"} & set(all_keys(trace)))

    if assessed:
        assert len(requests) == 1
        payload = requests[0]
        sent = {hit["chunk_id"]: hit for hit in payload["incidents"] + payload["documents"]}
        assert sent == {hit["chunk_id"]: hit for hit in expected}
        assert any(hit["service"] is None for hit in sent.values())
        assert set(payload["tool_results"]) == set(NAMES)
        assert payload["execution_context"]["context_mode"] == context_mode
        assert trace["risk_floor"] == "medium"
        assert trace["assessment"]["risk_level"] == "medium"
        assert all(question["severity"] == "medium" for question in trace["assessment"]["review_questions"])
        assert trace["tokens"] is None
    else:
        assert requests == []
        assert "Risk indication:" not in answer
