"""Offline tests: no Groq key or network needed. Run: uv run pytest -q

System 2 runs against FakeGroq, a stand-in that records each request and returns a
fixed structured answer, so these tests check what CRA2 sends and how it uses the reply.
"""

import importlib.util
import json
import time
from pathlib import Path
from types import SimpleNamespace

import groq
import pytest

from cra2 import config, system2
from cra2.__main__ import main
from cra2.advisor import ADVISORY, CATALOG, INCIDENTS, RULES, assess, context, grade, render

ROOT = Path(__file__).resolve().parent.parent
CASES = {c["id"]: c for c in json.loads((ROOT / "evals" / "cases.json").read_text())}
spec = importlib.util.spec_from_file_location("run_evals", ROOT / "scripts" / "run_evals.py")
run_evals = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_evals)

ANSWER = {
    "ratings": {"deploy_order": "medium", "rollback": "low", "config_drift": "none",
                "dependencies": "high", "monitoring": "medium"},
    "comments": [
        {"tag": "history", "severity": "high", "text": "Invented incident.", "evidence": ["CX-999"]},
        {"tag": "dependencies", "severity": "high", "text": "Five services sit downstream of the email queue.",
         "evidence": ["graph:notification-service.dependents"]},
        {"tag": "monitoring", "severity": "medium", "text": "Queue lag alert fires only after 5 minutes.",
         "evidence": ["change:monitoring_plan", "catalog:notification-service.monitors"]},
        {"tag": "rollback", "severity": "low", "text": "Scaling back is fast; rehearse it.",
         "evidence": ["change:rollback_plan"]},
    ],
}
UNSURE_LOW = {"id": "T-1", "service": "notification-service", "change_type": "Code deploy",
              "summary": "Batch email sends in groups of 50.", "rollback_plan": "Redeploy the previous image."}


class FakeGroq:
    """Stands in for groq.Groq: records every request and returns ANSWER."""

    def __init__(self, answer):
        self.answer, self.requests = answer, []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(
            model=kwargs["model"], system_fingerprint="fp_test",
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(self.answer)))],
            usage=SimpleNamespace(prompt_tokens=900, completion_tokens=250, total_time=0.21))


@pytest.fixture
def fake(monkeypatch):
    def install(answer=ANSWER):
        client = FakeGroq(answer)
        monkeypatch.setattr(system2, "client", lambda: client)
        system2.call.cache_clear()
        return client
    yield install
    system2.call.cache_clear()


# --- Data and ruleset ------------------------------------------------------------

def test_data_is_consistent():
    assert all(d in CATALOG for s in CATALOG.values() for d in s["depends_on"])
    assert all(i["service"] in CATALOG for i in INCIDENTS)
    assert len({i["incident_id"] for i in INCIDENTS}) == len(INCIDENTS)
    for c in CASES.values():
        assert c["change"]["service"] in CATALOG
        assert c["change"]["change_type"] in RULES["system1"]["change_type"]
        assert set(c["expected"]["cite_any"]) <= {i["incident_id"] for i in INCIDENTS}
        assert sum(item["points"] for item in c["rubric"]) == 10


def test_twenty_diverse_eval_cases():
    levels = [c["expected"]["level"] for c in CASES.values()]
    assert len(CASES) == 20 and all(levels.count(level) >= 5 for level in ("low", "medium", "high"))
    assert len({c["change"]["change_type"] for c in CASES.values()}) >= 6
    assert {c["change"]["service"] for c in CASES.values()} == set(CATALOG)


def test_thresholds_depend_on_system_type():
    assert [grade(0.25, tier) for tier in ("critical", "core", "standard")] == ["medium", "low", "low"]
    assert [grade(0.65, tier) for tier in ("critical", "core", "standard")] == ["high", "high", "medium"]
    assert grade(0.0, "standard", floor="high") == "high"


# --- System 1 ----------------------------------------------------------------------

@pytest.mark.parametrize("case_id", sorted(CASES))
def test_system1_matches_expected_level_with_three_grounded_comments(case_id):
    case = CASES[case_id]
    r = assess(case["change"], "fast")
    assert (r["level"], r["route"]) == (case["expected"]["level"], case["expected"]["route"])
    assert len(r["comments"]) == 3 and len({c["tag"] for c in r["comments"]}) == 3
    allowed = set(context(case["change"])["evidence"])
    assert all(c["evidence"] and set(c["evidence"]) <= allowed for c in r["comments"])
    assert render(r).endswith(ADVISORY)


def test_system1_answers_in_well_under_a_millisecond():
    changes = [c["change"] for c in CASES.values()]
    assess(changes[0], "fast")  # warm up
    timings = []
    for _ in range(25):
        for change in changes:
            t = time.perf_counter()
            assess(change, "fast")
            timings.append((time.perf_counter() - t) * 1000)
    assert sorted(timings)[int(0.95 * len(timings))] < 1.0


def test_freeze_window_is_high_without_calling_groq(fake):
    client = fake()
    r = assess(CASES["CHG-04"]["change"], "auto")
    assert r["level"] == "high" and r["path"] == "system1" and client.requests == []


# --- System 2 (Groq) -------------------------------------------------------------------

def test_groq_request_is_pinned_deterministic_and_structured(fake):
    client = fake()
    assess(CASES["CHG-06"]["change"], "deep")
    (req,) = client.requests
    assert req["model"] == config.MODEL and req["temperature"] == 0 and req["seed"] == config.SEED
    assert req["response_format"]["type"] == "json_schema" and req["response_format"]["json_schema"]["strict"]
    if config.MODEL.startswith("openai/gpt-oss"):
        assert req["reasoning_effort"] == "low"
    payload = json.loads(req["messages"][1]["content"])
    assert payload["change"] == CASES["CHG-06"]["change"] and "CX-111" in payload["evidence_keys"]


def test_real_groq_sdk_sends_and_parses_the_request(monkeypatch):
    """The real SDK over a mocked HTTP transport: catches SDK argument or response-shape mistakes."""
    import httpx

    sent = []

    def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={
            "id": "chatcmpl-test", "object": "chat.completion", "created": 0, "model": config.MODEL,
            "system_fingerprint": "fp_test",
            "choices": [{"index": 0, "finish_reason": "stop", "logprobs": None,
                         "message": {"role": "assistant", "content": json.dumps(ANSWER)}}],
            "usage": {"prompt_tokens": 900, "completion_tokens": 250, "total_tokens": 1150, "total_time": 0.21}})

    sdk = groq.Groq(api_key="test", max_retries=0, http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(system2, "client", lambda: sdk)
    system2.call.cache_clear()
    r = assess(CASES["CHG-06"]["change"], "deep")
    system2.call.cache_clear()
    assert r["system2"] == {"score": r["system2"]["score"], "model": config.MODEL, "fingerprint": "fp_test",
                            "tokens": [900, 250], "groq_ms": 210}
    (body,) = sent
    assert body["temperature"] == 0 and body["seed"] == config.SEED and body["response_format"]["json_schema"]["strict"]


def test_same_change_five_times_gives_the_same_answer(fake):
    fake()
    answers = []
    for _ in range(5):
        system2.call.cache_clear()
        r = assess(CASES["CHG-06"]["change"], "deep")
        answers.append((r["level"], r["route"], json.dumps(r["comments"])))
    assert len(set(answers)) == 1


def test_repeat_question_is_served_from_cache(fake):
    client = fake()
    first, second = (assess(CASES["CHG-16"]["change"], "auto") for _ in range(2))
    assert first["path"] == second["path"] == "system2" and len(client.requests) == 1
    assert first["comments"] == second["comments"]


def test_system2_comments_must_cite_given_evidence(fake):
    fake()
    r = assess(CASES["CHG-06"]["change"], "deep")
    assert r["path"] == "system2" and "CX-999" not in json.dumps(r["comments"])
    assert [c["tag"] for c in r["comments"]] == ["dependencies", "monitoring", "rollback"]


def test_system2_score_is_blended_with_system1(fake):
    fake()
    r = assess(CASES["CHG-06"]["change"], "deep")
    ratings = [RULES["system2"]["rating_value"][v] for v in ANSWER["ratings"].values()]
    s2 = round(0.6 * max(ratings) + 0.4 * sum(ratings) / len(ratings), 2)
    assert r["system2"]["score"] == s2 and r["score"] == round(0.5 * r["system1_score"] + 0.5 * s2, 2)


def test_unsure_change_fails_closed_when_groq_is_unavailable(monkeypatch):
    def no_key():
        raise groq.GroqError("The api_key client option must be set")
    monkeypatch.setattr(system2, "client", no_key)
    system2.call.cache_clear()
    r = assess(UNSURE_LOW, "auto")
    assert grade(r["system1_score"], "standard") == "low"  # System 1 alone would auto-approve...
    assert r["level"] == "medium" and r["route"] == "review" and "unavailable" in r["note"]  # ...but it is unsure


def test_groq_can_never_put_an_unsure_change_in_the_auto_approve_lane(fake):
    fake({**ANSWER, "ratings": dict.fromkeys(ANSWER["ratings"], "none")})
    r = assess(UNSURE_LOW, "auto")
    assert r["path"] == "system2" and grade(r["score"], "standard") == "low"  # the blended score says low...
    assert r["level"] == "medium" and r["route"] == "review"  # ...but only System 1 may auto-approve


# --- Prompt, schema, CLI, eval scorer ----------------------------------------------

def test_prompt_and_schema_hold_the_rules():
    for phrase in ("paranoid", "evidence_keys", "exactly three comments", "Never approve, block, merge or deploy"):
        assert phrase in " ".join(system2.PROMPT.split())

    def strict(node):  # Groq strict mode: every object lists all its properties and allows no others
        if node.get("type") == "object":
            assert node["additionalProperties"] is False and set(node["required"]) == set(node["properties"])
        for child in [*node.get("properties", {}).values(), node.get("items", {})]:
            if child:
                strict(child)
    strict(system2.SCHEMA)


def test_cli(capsys):
    main(["CHG-02", "--mode", "fast"])
    assert capsys.readouterr().out.strip().endswith(ADVISORY)
    main(["CHG-02", "--mode", "fast", "--json"])
    assert json.loads(capsys.readouterr().out)["route"] == "auto-approve"
    with pytest.raises(SystemExit):
        main(["no-such-change.json"])


def test_eval_scorer_gives_full_marks_only_for_the_expected_answer():
    case = CASES["CHG-01"]
    r = assess(case["change"], "fast")
    assert sum(run_evals.mark(case, r).values()) == 10
    lower = {**r, "level": "medium", "route": "review"}
    assert run_evals.mark(case, lower)["level"] == 0 and run_evals.mark(case, lower)["route"] == 0
