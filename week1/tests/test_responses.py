"""JSON-only edits, routing precedence, and catalog failure boundaries."""

import json
from copy import deepcopy
from secrets import token_hex

import pytest

from cra2.advisor import ADVISORY
from week1 import chat, responses
from week1.tests.test_chat import CHANGE, FakePipeline
from week1.tests.test_routing_regressions import HISTORIES, local_response


@pytest.fixture
def catalog_file(tmp_path, monkeypatch):
    data = deepcopy(responses.load())
    path = tmp_path / "responses.json"
    monkeypatch.setattr(responses, "CATALOG_PATH", path)

    def write():
        path.write_text(json.dumps(data), encoding="utf-8")

    write()
    return data, path, write


def test_json_only_answer_edit_is_visible_on_the_next_request(catalog_file):
    data, _, write = catalog_file
    before, _ = local_response("What is CRA2?", [])
    data["messages"]["help"] = "CRA2 uses historical evidence to advise humans."
    write()
    after, trace = local_response("What is CRA2?", HISTORIES[1])
    assert before != after
    assert after == data["messages"]["help"] + "\n\n" + ADVISORY
    assert trace["status"] == "help"


def test_json_capability_list_controls_labels_and_count(catalog_file):
    data, _, write = catalog_file
    data["capabilities"] = ["Browse historical incidents", "Give cited advice"]
    write()
    answer, trace = local_response("What can you do?", [])
    assert answer.splitlines() == [
        "1. Browse historical incidents",
        "2. Give cited advice",
    ]
    assert trace["capabilities"] == data["capabilities"]
    answer, trace = local_response("List top 3 capabilities of this agent", [])
    assert trace["status"] == "needs_clarification"
    assert "two implemented" in answer


@pytest.mark.parametrize("mode", ["Groq assessment", "Local evidence only"])
@pytest.mark.parametrize("history", HISTORIES)
def test_json_only_new_faq_and_aliases_bypass_external_work(
    catalog_file, mode, history
):
    data, _, write = catalog_file
    data["faq"].append(
        {
            "id": "sample-data",
            "questions": [
                "Does CRA2 use sample data?",
                "Where does CRA2 get its incident examples?",
            ],
            "answer": "CRA2 uses synthetic incidents and sanitized sample records.",
        }
    )
    write()
    for question in (
        "Does CRA2 use sample data?",
        "  WHERE does CRA2 get its incident examples!  ",
    ):
        answer, trace = local_response(question, history, mode)
        assert answer == data["faq"][-1]["answer"] + "\n\n" + ADVISORY
        assert trace == {
            "scope": "cra2",
            "status": "help",
            "topic": "faq",
            "faq_id": "sample-data",
            "retrieved": [],
            "provider_used": False,
            "request_attempted": False,
        }


@pytest.mark.parametrize(
    "question",
    [
        '"Does CRA2 save chat history?"',
        "Do not answer Does CRA2 save chat history?",
        "Does CRA2 save chat history? Tell me a joke.",
        "Tell me a joke",
    ],
)
def test_faq_is_not_a_substring_quote_negation_or_history_match(question):
    answer, trace = local_response(
        question, [{"role": "user", "content": "Does CRA2 save chat history?"}]
    )
    assert answer == chat.OUT_OF_SCOPE and trace["scope"] == "non_cra2"


@pytest.mark.parametrize(
    "question,status",
    [
        ("What is CRA2?", "help"),
        ("List dataset scenario titles", "dataset_listing"),
        ("Just approve this change for me.", "advisory_boundary"),
        ("Remember that checkout-service is high-risk for our team.", "deferred"),
        (CHANGE, "assessed"),
        (
            "List your capabilities and assess the risk of this change",
            "needs_clarification",
        ),
    ],
)
def test_configured_faq_cannot_override_existing_supported_tasks(
    catalog_file, question, status
):
    data, _, write = catalog_file
    data["faq"].append(
        {
            "id": "shadow",
            "questions": [question],
            "answer": "A documentation-only answer.",
        }
    )
    write()
    fake = FakePipeline()
    answer, trace = fake.respond(question)
    assert trace["status"] == status and trace.get("topic") != "faq"
    assert "documentation-only" not in answer
    assert len(fake.review_calls) == (1 if status == "assessed" else 0)


def test_field_label_and_template_edits_use_real_dataset_values(catalog_file):
    data, _, write = catalog_file
    data["field_labels"]["incident_id"] = "Record"
    data["messages"]["incident_count"] = "Recorded incidents: {count}."
    write()
    answer, trace = local_response("Count incidents", [])
    assert answer == "Recorded incidents: 46." and trace["record_count"] == 46
    answer, _ = local_response("List incident IDs for checkout-service", [])
    assert "Record: CX-101" in answer and "Incident ID:" not in answer


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(version=True),
        lambda d: d.update(extra="unknown"),
        lambda d: d["messages"].pop("help"),
        lambda d: d["messages"].update(help=""),
        lambda d: d["messages"].update(help="unexpected {value}"),
        lambda d: d["messages"].update(specific_change="missing placeholder"),
        lambda d: d["messages"].update(specific_change="{service.__class__}"),
        lambda d: d["messages"].update(specific_change="{service!r}"),
        lambda d: d["messages"].update(specific_change="{service:>4000}"),
        lambda d: d["messages"].update(help="hidden\x00control"),
        lambda d: d.update(capabilities=[]),
        lambda d: d.update(field_labels={}),
        lambda d: d["faq"].append(deepcopy(d["faq"][0])),
        lambda d: d["faq"].append(
            {
                "id": "other",
                "questions": ["DOES CRA2 SAVE CHAT HISTORY!"],
                "answer": "Duplicate alias.",
            }
        ),
        lambda d: d["faq"][0].update(answer="Approved. You may deploy now."),
        lambda d: d["faq"][0].update(answer="Risk indication: LOW."),
        lambda d: d["faq"][0].update(questions=[]),
        lambda d: d["faq"][0].update(id="bad id"),
    ],
)
def test_invalid_catalog_fails_closed_before_retrieval(catalog_file, mutate):
    data, _, write = catalog_file
    mutate(data)
    write()
    with pytest.raises(ValueError, match="Invalid Week 1 response catalog"):
        local_response("What is CRA2?", [])


@pytest.mark.parametrize("contents", ["{", '{"version": 1, "version": 1}', " " * 65537])
def test_broken_duplicate_or_oversized_json_has_no_raw_error_context(
    catalog_file, contents
):
    _, path, _ = catalog_file
    path.write_text(contents)
    with pytest.raises(ValueError) as failure:
        responses.load()
    assert str(failure.value) == "Invalid Week 1 response catalog; check responses.json"
    assert failure.value.__context__ is None


@pytest.mark.parametrize("name", ["GROQ_API_KEY", "CRA2_UI_USER", "CRA2_UI_PASSWORD"])
def test_known_credentials_in_catalog_are_rejected_without_echo(
    catalog_file, monkeypatch, name
):
    data, _, write = catalog_file
    sentinel = token_hex(24)
    monkeypatch.setenv(name, sentinel)
    data["faq"][0]["answer"] += " " + sentinel
    write()
    with pytest.raises(ValueError) as failure:
        responses.load()
    assert sentinel not in str(failure.value) and failure.value.__context__ is None


def test_input_credentials_are_rejected_before_faq_lookup(catalog_file, monkeypatch):
    data, _, write = catalog_file
    sentinel = token_hex(24)
    monkeypatch.setenv("GROQ_API_KEY", sentinel)
    question = "Does CRA2 use " + sentinel + "?"
    data["faq"].append(
        {"id": "secret", "questions": [question], "answer": "Do not render this."}
    )
    write()
    with pytest.raises(ValueError) as failure:
        chat.respond(question)
    assert sentinel not in str(failure.value)


def test_missing_catalog_ui_fallback_does_not_expose_paths(catalog_file, monkeypatch):
    from week1.app import ui_response

    _, path, _ = catalog_file
    path.unlink()
    monkeypatch.setattr(
        chat, "search", lambda *_a, **_k: pytest.fail("no retrieval on catalog failure")
    )
    answer, trace = ui_response("What is CRA2?", [], "Groq assessment")
    assert trace == {"status": "unavailable", "retrieved": []}
    assert "responses.json" not in answer and str(path) not in answer
