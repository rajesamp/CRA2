"""Week 2 app help is current, catalog-backed, local and bounded by intent."""

import pytest

from week2 import workflow


def forbidden(*_args, **_kwargs):
    pytest.fail("App help must not retrieve, call MCP or use a provider")


@pytest.mark.parametrize("mode", ["Local evidence only", "Groq assessment"])
@pytest.mark.parametrize("question,topic", [
    ("What is this app?", "overview"),
    ("Help me", "overview"),
    ("What is this app helping with?", "overview"),
    ("How can this app help me?", "overview"),
    ("Tell me about CRA2.", "overview"),
    ("How does CRA2 work?", "overview"),
    ("What can you do?", "capabilities"),
    ("List the known services.", "services"),
    ("What services do you support?", "services"),
    ("Which services are available?", "services"),
    ("How do I get started?", "examples"),
    ("What should I ask?", "examples"),
    ("What is the difference between Local evidence only and Groq assessment?", "modes"),
    ("Does this app use an LLM for every question?", "modes"),
    ("Does this app remember preferences?", "memory"),
    ("How do I save a preference?", "preference_commands"),
    ("Does this app save chat history?", "memory"),
    ("Does CRA2 restore previous conversations?", "memory"),
    ("How does agent trace work?", "trace"),
    ("How do I open the Admin panel?", "trace"),
    ("Where is the Admin tab?", "trace"),
    ("What are the limitations of this app?", "limits"),
    ("Can this app approve changes?", "limits"),
    ("How does this app use MCP?", "tools"),
    ("Does this app use LangGraph?", "tools"),
    ("How does the classifier work?", "security"),
    ("How does this app prevent prompt injection?", "security"),
])
def test_app_help_does_not_leave_the_local_help_path(question, topic, mode):
    answer, trace = workflow.respond(question, mode=mode, retriever=forbidden,
                                     reviewer=forbidden, tool_runner=forbidden)
    assert trace["status"] == "help" and trace["topic"] == topic
    assert "outside CRA2" not in answer
    assert trace["provider_used"] is False and trace["request_attempted"] is False
    assert not trace["retrieved"]


def test_known_services_come_from_current_catalog(monkeypatch):
    monkeypatch.setattr(workflow, "CATALOG", {"new-service": {}, "another-service": {}})
    answer, trace = workflow.respond("List known services", retriever=forbidden, reviewer=forbidden, tool_runner=forbidden)
    assert trace["status"] == "help"
    assert "new-service" in answer and "another-service" in answer
    assert "checkout-service" not in answer


def test_trace_help_explains_admin_demo_gate_and_history():
    answer, trace = workflow.respond("How does agent trace work?", retriever=forbidden,
                                    reviewer=forbidden, tool_runner=forbidden)
    assert trace["topic"] == "trace"
    assert "Admin" in answer and "four digits" in answer and "not owner authentication" in answer
    assert "50" in answer and "Retry" in answer and "undo" in answer


def test_capability_count_and_current_week2_features():
    answer, trace = workflow.respond("List your top three capabilities.", retriever=forbidden,
                                     reviewer=forbidden, tool_runner=forbidden)
    assert trace["status"] == "help" and trace["topic"] == "capabilities"
    assert len([line for line in answer.splitlines() if line[:1].isdigit()]) == 3
    answer, _ = workflow.respond("What can you do?", retriever=forbidden, reviewer=forbidden, tool_runner=forbidden)
    assert "preferences" in answer and "trace" in answer
    assert "not available in this demo" not in answer
    answer, trace = workflow.respond("List your top six capabilities.", retriever=forbidden, reviewer=forbidden, tool_runner=forbidden)
    assert trace["status"] == "help" and len([line for line in answer.splitlines() if line[:1].isdigit()]) == 6
    answer, trace = workflow.respond("List your top 7 capabilities.", retriever=forbidden, reviewer=forbidden, tool_runner=forbidden)
    assert trace["status"] == "needs_clarification" and "6" in answer


def test_help_does_not_swallow_unrelated_or_mixed_requests():
    for question, status in [
        ("What's the capital of France?", "out_of_scope"),
        ("How do I use pandas?", "out_of_scope"),
        ("What can you do and assess checkout-service config timeout from 4 seconds to 400 milliseconds?", "needs_clarification"),
        ("Please approve checkout-service timeout change now", "advisory_boundary"),
    ]:
        _, trace = workflow.respond(question, retriever=forbidden, reviewer=forbidden, tool_runner=forbidden)
        assert trace["status"] == status
