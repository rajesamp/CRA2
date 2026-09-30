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

    for question in ("Hello", "Change the timeout from 4 seconds to 400 milliseconds."):
        chat.respond(question, HISTORIES[1], "Local evidence only", retriever=retrieve)
    assert calls[0]["service"] is None
    assert calls[1]["service"] == "checkout-service"


def test_unknown_api_cannot_inherit_previous_service():
    calls = []
    chat.respond(
        "Change nonexistent-api timeout from 4 seconds to 400 milliseconds.",
        HISTORIES[1],
        retriever=lambda *a, **kw: calls.append(kw) or [],
    )
    assert calls[0]["service"] is None
