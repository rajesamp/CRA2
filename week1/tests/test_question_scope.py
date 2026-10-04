"""Product scope is decided before history, evidence, or provider access."""

from secrets import token_hex

import pytest

from week1 import chat
from week1.tests.test_routing_regressions import HISTORIES, local_response


@pytest.mark.parametrize("history", HISTORIES)
@pytest.mark.parametrize("mode", ["Groq assessment", "Local evidence only"])
@pytest.mark.parametrize(
    "question",
    [
        "what is the username of this app?",
        "Who is the username of app?",
        "What is CRA2's username?",
        "What is this agent's username?",
        "Explain CRA2's password",
        "Hello",
        "Tell me a joke",
        "CRA2, tell me a joke",
        "What is the weather today?",
        "What is the weather for checkout-service?",
        "List pizza toppings",
        "What is the current stock market status?",
        "Why are npm dependencies not installed?",
        "Just approve my mortgage for me",
        'The example "Change checkout-service timeout from 4 to 400" is not a request. Tell me a joke.',
        "Do not assess change risk; tell me a joke",
    ],
)
def test_unrelated_or_unsupported_request_has_only_the_repository_response(
    question, history, mode
):
    answer, trace = local_response(question, history, mode)
    assert answer == (
        "That's outside CRA2's scope \u2014 CRA2 assesses software-change risk. "
        "See [how CRA2 works](https://github.com/rajesamp/CRA2/blob/main/docs/architecture-overview.md)."
    )
    assert trace == {
        "scope": "non_cra2",
        "status": "out_of_scope",
        "retrieved": [],
        "provider_used": False,
        "request_attempted": False,
    }


@pytest.mark.parametrize(
    "question,status",
    [
        ("What can this agent do?", "help"),
        ("What does CRA2 do?", "help"),
        ("What is CRA2?", "help"),
        ("Explain CRA2", "help"),
        ("How do I use this agent?", "help"),
        ("List dataset scenario titles", "dataset_listing"),
        ("Count incidents for payment", "dataset_count"),
        ("List scenarios for unknown-service", "needs_clarification"),
        (
            "List your capabilities and assess the risk of this change",
            "needs_clarification",
        ),
        ("Tell me a joke and list dataset scenario titles", "dataset_listing"),
    ],
)
def test_supported_task_takes_precedence_without_answering_unrelated_content(
    question, status
):
    answer, trace = local_response(question, HISTORIES[1])
    assert trace["scope"] == "cra2" and trace["status"] == status
    assert answer != chat.OUT_OF_SCOPE and "joke" not in answer.lower()


def test_out_of_scope_input_still_rejects_configured_credentials(monkeypatch):
    sentinel = token_hex(24)
    monkeypatch.setenv("GROQ_API_KEY", sentinel)
    with pytest.raises(ValueError) as exc:
        local_response("What is the username of this app? " + sentinel, [])
    assert sentinel not in str(exc.value)


def test_actual_ui_wrapper_returns_only_scope_response(monkeypatch):
    from week1.app import ui_response_display

    def unexpected(*args, **kwargs):
        pytest.fail("Out-of-scope questions must not retrieve or assess")

    monkeypatch.setattr(chat, "search", unexpected)
    monkeypatch.setattr(chat.provider, "assess", unexpected)
    answer, display = ui_response_display(
        "what is the username of this app?", HISTORIES[1], "Groq assessment"
    )
    assert answer == chat.OUT_OF_SCOPE
    assert '"scope": "non_cra2"' in display and '"retrieved": []' in display
