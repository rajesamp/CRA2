"""Regression proofs for validation and deterministic risk policy boundaries."""

import copy
import json
from pathlib import Path

import pytest

from cra2 import advisor, system2

CASES = json.loads(
    (Path(__file__).resolve().parents[1] / "evals" / "cases.json").read_text()
)
CHANGE = CASES[4]["change"]


@pytest.mark.parametrize(
    "change",
    [
        None,
        [],
        "change",
        42,
        {**CHANGE, "service": []},
        {**CHANGE, "rollback_plan": 42},
        {**CHANGE, "summary": "x" * 10001},
        {**CHANGE, "secret": "extra data"},
    ],
)
def test_invalid_inputs_raise_value_error(change):
    with pytest.raises(ValueError):
        advisor.assess(change, "fast")


def test_whitespace_and_null_plans_are_missing_and_input_is_not_mutated():
    change = {**CHANGE, "rollback_plan": "\t\n", "monitoring_plan": None}
    before = copy.deepcopy(change)
    empty = {**change, "rollback_plan": "", "monitoring_plan": ""}
    actual, expected = (advisor.assess(c, "fast") for c in (change, empty))
    assert actual["score"] == expected["score"]
    assert actual["comments"] == expected["comments"]
    assert change == before


@pytest.mark.parametrize("mode", ["FAST", "deeep", "", False, []])
def test_invalid_modes_are_rejected(mode):
    with pytest.raises(ValueError, match="Mode"):
        advisor.assess(CHANGE, mode)


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -0.1, 1.1, True, "0.5"])
def test_invalid_scores_are_rejected(score):
    with pytest.raises(ValueError, match="score"):
        advisor.grade(score, "core")


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_model_cannot_reduce_rule_based_risk(case, monkeypatch):
    monkeypatch.setattr(
        system2,
        "assess",
        lambda *_: {
            "score": 0,
            "out": {"comments": []},
            "model": "test",
            "fingerprint": None,
            "tokens": [1, 1],
            "groq_ms": None,
            "cache_hit": False,
            "request_attempted": True,
        },
    )
    baseline = advisor.assess(case["change"], "fast")
    deep = advisor.assess(case["change"], "deep")
    assert advisor.LEVELS.index(deep["level"]) >= advisor.LEVELS.index(
        baseline["level"]
    )
    assert deep["risk_floor"] == baseline["level"]
    assert deep["advisory"] == advisor.ADVISORY


def test_cycles_do_not_count_service_as_its_own_dependent(monkeypatch):
    catalog = copy.deepcopy(advisor.CATALOG)
    catalog["notification-service"]["depends_on"] = ["payment-gateway"]
    monkeypatch.setattr(advisor, "CATALOG", catalog)
    change = {**CHANGE, "service": "notification-service"}
    ctx = advisor.context(change)
    assert "payment-gateway" in ctx["dependents"]
    assert "notification-service" not in ctx["dependents"]


def test_provider_failure_keeps_rule_result_and_usage(monkeypatch):
    def fail(*_):
        raise system2.System2Unavailable(
            "bad response", request_attempted=True, tokens=[200, 30], groq_ms=90
        )

    monkeypatch.setattr(system2, "assess", fail)
    result = advisor.assess(CHANGE, "deep")
    assert result["path"] == "system1" and result["system2"] is None
    assert result["system2_attempted"] and result["system2_request_attempted"]
    assert result["system2_failure_usage"] == {"tokens": [200, 30], "groq_ms": 90}
    assert result["score"] == result["system1_score"]


def test_catalog_evidence_keys_have_facts_in_provider_payload(monkeypatch):
    captured = []

    def fail(payload, _):
        captured.append(payload)
        raise system2.System2Unavailable("No provider needed")

    monkeypatch.setattr(system2, "assess", fail)
    for case in CASES:
        advisor.assess(case["change"], "deep")
    for payload in captured:
        catalog = {
            payload["service"]["name"]: payload["service"],
            **payload["direct_dependencies"],
        }
        for key in payload["evidence_keys"]:
            if key.startswith("catalog:"):
                service, field = key.removeprefix("catalog:").split(".")
                assert field in catalog[service]


def test_rule_hazards_win_same_severity_comment_ties(monkeypatch):
    change = next(c["change"] for c in CASES if c["id"] == "CHG-01")
    monkeypatch.setattr(
        system2,
        "assess",
        lambda *_: {
            "score": 1,
            "model": "test",
            "fingerprint": None,
            "tokens": [1, 1],
            "groq_ms": None,
            "cache_hit": False,
            "request_attempted": True,
            "out": {
                "comments": [
                    {
                        "tag": tag,
                        "severity": "high",
                        "text": "Model comment.",
                        "evidence": ["change:summary"],
                    }
                    for tag in ("dependencies", "monitoring", "rollback")
                ]
            },
        },
    )
    assert advisor.assess(change, "deep")["comments"][0]["tag"] == "history"


def test_rendered_user_text_cannot_add_markdown_or_terminal_controls():
    result = advisor.assess(
        {**CHANGE, "rollback_plan": "[click](https://example.com)\n<b>"}, "fast"
    )
    rendered = advisor.render(result)
    assert (
        "[click](" not in rendered and "\x1b" not in rendered and "<b>" not in rendered
    )
    assert rendered.endswith(advisor.ADVISORY)


@pytest.mark.parametrize("text", ["\u200b", "\x00", "\x1b[31m", "\u202e", "\ud800"])
@pytest.mark.parametrize(
    "field", ["summary", "rollback_plan", "monitoring_plan", "deploy_plan"]
)
def test_invisible_plans_cannot_bypass_missing_plan_penalties(text, field):
    with pytest.raises(ValueError, match="control or invisible"):
        advisor.assess({**CHANGE, field: text}, "fast")
