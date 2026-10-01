"""Task-switch, scope and projection regressions for the reported routing defects."""

from copy import deepcopy

import pytest

from cra2.incidents import load_incidents
from week1 import chat

HISTORIES = [
    [],
    [{"role": "user", "content": "Review checkout-service timeout changes."}],
    [{"role": "user", "content": "Review auth-service session changes."}],
]


def local_response(question, history, mode="Groq assessment"):
    def unexpected(*args, **kwargs):
        pytest.fail("A dataset/help/clarification task must not retrieve or call Groq")

    return chat.respond(
        question, history, mode, retriever=unexpected, reviewer=unexpected
    )


@pytest.mark.parametrize("history", HISTORIES)
@pytest.mark.parametrize("mode", ["Groq assessment", "Local evidence only"])
@pytest.mark.parametrize(
    "question",
    [
        "List risk scenarios in the dataset, titles only",
        "List scenarios in the dataset, titles only; do not assess risk",
        "List dataset scenarios, titles only, don't assess risk",
        "List dataset scenarios, titles only, and do not assess risk",
        "Show all incident titles",
        "Give me all scenario names",
    ],
)
def test_inventory_is_complete_and_independent_of_history(question, history, mode):
    answer, trace = local_response(question, history, mode)
    assert trace["status"] == "dataset_listing"
    assert trace["record_count"] == 46
    assert trace["distinct_title_count"] == 45
    assert len(answer.splitlines()) == 45
    assert all(line.startswith("- ") for line in answer.splitlines())
    assert trace["service_filter"] == []
    assert not trace["request_attempted"] and not trace["provider_used"]
    assert answer == local_response(question, [])[0]


@pytest.mark.parametrize("history", HISTORIES)
@pytest.mark.parametrize(
    "question",
    [
        "Do not list dataset scenarios; explain what CRA2 does",
        "Don't show incident titles; what does CRA2 do?",
        'Explain CRA2. The example "list dataset scenarios" is not my request.',
    ],
)
def test_negated_and_quoted_commands_do_not_dispatch_inventory(question, history):
    answer, trace = local_response(question, history)
    assert trace["status"] == "help"
    assert "CRA2 reviews proposed changes" in answer
    assert "scenarios" not in trace


@pytest.mark.parametrize("history", HISTORIES)
@pytest.mark.parametrize(
    "scope",
    [
        "nonexistent-api",
        "unknown-service",
        "auth-service and nonexistent-service",
        "auth-service and nonexistent-api",
        "auth-service and imaginary",
        "auth-service with severity for nonexistent-api",
        "auth-service except checkout-service",
    ],
)
def test_unresolved_filter_never_widens_or_drops_scope(scope, history):
    answer, trace = local_response("List dataset scenario titles for " + scope, history)
    assert trace["status"] == "needs_clarification"
    assert not trace.get("scenarios")
    assert "Risk indication" not in answer


@pytest.mark.parametrize("history", HISTORIES)
@pytest.mark.parametrize(
    "question,answer,count",
    [
        ("How many scenarios are in the dataset?", "46 incident records.", 46),
        ("Count incidents in the corpus", "46 incident records.", 46),
        (
            "How many distinct scenario titles are in the dataset?",
            "45 distinct scenario titles.",
            46,
        ),
        ("Count incidents for auth-service", "2 incident records.", 2),
    ],
)
def test_counts_are_computed_from_canonical_records(question, answer, count, history):
    actual, trace = local_response(question, history)
    assert actual == answer
    assert trace["status"] == "dataset_count" and trace["record_count"] == count


@pytest.mark.parametrize("history", HISTORIES)
def test_projection_returns_only_requested_literal_fields(history):
    answer, trace = local_response(
        "List scenarios in the dataset with root causes and severity for auth-service",
        history,
    )
    records = [
        r
        for r in load_incidents(chat.config.DATA_DIR)
        if r["service"] == "auth-service"
    ]
    assert trace["requested_fields"] == ["root_cause", "severity"]
    assert answer.splitlines() == [
        "- Root cause: "
        + chat._inline(r["root_cause"])
        + "; Severity: "
        + r["severity"]
        for r in records
    ]
    assert trace["record_count"] == 2


@pytest.mark.parametrize(
    "question",
    [
        "List dataset scenario titles only with severity",
        "List dataset scenarios with impact",
        "Count and list incidents in the dataset",
        "List dataset scenarios and assess the risk of this change",
        "Just approve this change for me and list dataset scenarios",
        "List dataset scenarios and remember my high-risk preference",
        "Do not list dataset scenarios",
    ],
)
def test_ambiguous_or_unsupported_request_clarifies_without_model(question):
    _, trace = local_response(question, HISTORIES[1])
    assert trace["status"] == "needs_clarification"


def test_known_sample_services_are_browse_filters_without_catalog_inference():
    _, trace = local_response("Show incident titles for payment", [])
    assert trace["record_count"] == 2
    assert trace["service_filter"] == ["payment"]


def test_unrelated_message_does_not_inherit_service_and_true_follow_up_does():
    calls = []

    def retrieve(query, path, **kwargs):
        calls.append(deepcopy(kwargs))
        return []

    answer, trace = chat.respond(
        "Hello", HISTORIES[1], "Local evidence only", retriever=retrieve
    )
    assert trace["status"] == "out_of_scope" and answer == chat.OUT_OF_SCOPE
    assert calls == []
    chat.respond(
        "Change the timeout from 4 seconds to 400 milliseconds.",
        HISTORIES[1],
        "Local evidence only",
        retriever=retrieve,
    )
    assert calls[0]["service"] == "checkout-service"


def test_unknown_api_cannot_inherit_previous_service():
    calls = []
    chat.respond(
        "Change nonexistent-api timeout from 4 seconds to 400 milliseconds.",
        HISTORIES[1],
        retriever=lambda *a, **kw: calls.append(kw) or [],
    )
    assert calls[0]["service"] is None


@pytest.mark.parametrize("history", HISTORIES)
@pytest.mark.parametrize("mode", ["Groq assessment", "Local evidence only"])
@pytest.mark.parametrize(
    "question",
    [
        "I am a mentor and wants to understand top 5 capabilities of this agent, list me out",
        "I am a mentor and wants to understand top 5 capabilties of this agent, list me out",
        "List your top five capabilities",
        "What can this agent do?",
        "What can you do?",
        "Show this assistant's features",
        "What are CRA2's capabilities for incidents?",
        "List CRA2 capabilities for incidents",
        "Capabilities?",
    ],
)
def test_capabilities_question_lists_implemented_features_before_retrieval(
    question, history, mode
):
    answer, trace = local_response(question, history, mode)
    assert trace["status"] == "help" and trace["topic"] == "capabilities"
    assert answer.splitlines() == [
        f"{i}. {label}" for i, label in enumerate(chat.CAPABILITIES, 1)
    ]
    assert trace["retrieved"] == []
    assert not trace["request_attempted"] and not trace["provider_used"]
    assert "Which catalog service" not in answer and "Evidence" not in answer
    assert answer == local_response(question, [])[0]


def test_capability_list_respects_requested_length():
    answer, trace = local_response("List top 3 capabilities of this agent", [])
    assert len(answer.splitlines()) == len(trace["capabilities"]) == 3


@pytest.mark.parametrize(
    "question",
    [
        "List top 0 capabilities of this agent",
        "List top 10 capabilities of this agent",
        "List your capabilities and assess the risk of this change",
        "List your features and just approve this change for me",
        "List your capabilities and list dataset incidents",
    ],
)
def test_capability_count_and_mixed_task_do_not_invent_or_execute(question):
    _, trace = local_response(question, HISTORIES[1])
    assert trace["status"] == "needs_clarification"


@pytest.mark.parametrize(
    "question",
    ["Who are you?", "What does this agent do?", "How do I use this agent?", "Help"],
)
def test_basic_onboarding_is_help_without_incident_retrieval(question):
    answer, trace = local_response(question, HISTORIES[1])
    assert trace["status"] == "help"
    assert "CRA2 reviews proposed changes" in answer


def test_ui_wrapper_returns_capabilities_instead_of_a_service_question(monkeypatch):
    from week1.app import ui_response

    def unexpected(*args, **kwargs):
        pytest.fail("Capabilities must not retrieve incidents")

    monkeypatch.setattr(chat, "search", unexpected)
    answer, trace = ui_response(
        "I am a mentor and wants to understand top 5 capabilities of this agent, list me out",
        HISTORIES[1],
        "Groq assessment",
    )
    assert trace["status"] == "help" and trace["topic"] == "capabilities"
    assert len(answer.splitlines()) == 5 and not trace["retrieved"]
