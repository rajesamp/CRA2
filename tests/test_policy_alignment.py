"""Meeting decisions: contextual advice, clarification, and explicit authority."""

import copy

import pytest

from cra2 import advisor, system2

CHANGE = {
    "service": "notification-service",
    "change_type": "Code deploy",
    "summary": "Fix spelling in the email footer.",
    "deploy_plan": "Rolling release.",
    "rollback_plan": "Restore prior image.",
    "monitoring_plan": "Watch email delivery error rate.",
}


@pytest.mark.parametrize(
    "patch",
    [
        {"summary": ""},
        {"summary": "Please assess the risk of this change"},
        {"summary": "Update notification-service"},
        {"summary": "minor changes"},
        {"service": "unknown-service"},
        {"change_type": "Update"},
    ],
)
def test_underspecified_input_asks_questions_without_scoring_or_model(
    patch, monkeypatch
):
    def unexpected(*args):
        pytest.fail("Clarification must precede scoring, retrieval and provider calls")

    monkeypatch.setattr(advisor, "context", unexpected)
    monkeypatch.setattr(system2, "assess", unexpected)
    result = advisor.assess({**CHANGE, **patch}, "deep")
    assert result["status"] == "needs_clarification"
    assert result["questions"]
    assert result["score"] is result["level"] is result["route"] is None
    assert not result["comments"] and not result["incident_context"]
    assert not result["system2_attempted"] and not result["system2_request_attempted"]
    assert "More detail needed" in advisor.render(result)


def test_empty_request_gets_targeted_questions():
    result = advisor.assess({}, "fast")
    assert len(result["questions"]) == 3
    assert result["status"] == "needs_clarification"


def test_freeze_alone_does_not_change_score_or_risk_level(monkeypatch):
    monkeypatch.setattr(advisor, "TEAM_SETTINGS", {"team": "test-team", "services": {}})
    baseline = advisor.assess(CHANGE, "fast")
    result = advisor.assess(
        {**CHANGE, "settings": {"freeze_window_active": True}}, "fast"
    )
    assert result["score"] == baseline["score"]
    assert result["level"] == baseline["level"] == "low"
    assert result["route"] == "routine-review"
    assert result["freeze"] == {
        "status": "unconfirmed",
        "reported_active": True,
        "evidence": ["change:settings.freeze_window_active"],
    }
    assert result["questions"] and "unconfirmed" in advisor.render(result)
    assert any(c["tag"] == "freeze" for c in result["comments"])


def test_team_override_and_conflict_are_exposed_to_user_and_provider(monkeypatch):
    monkeypatch.setattr(
        advisor,
        "TEAM_SETTINGS",
        {
            "team": "test-team",
            "services": {
                "notification-service": {
                    "freeze_window_active": True,
                    "high_risk": True,
                }
            },
        },
    )
    captured = []

    def capture(payload, rules):
        captured.append(payload)
        raise system2.System2Unavailable("offline")

    monkeypatch.setattr(system2, "assess", capture)
    change = {**CHANGE, "settings": {"freeze_window_active": False, "high_risk": False}}
    original = copy.deepcopy(change)
    result = advisor.assess(change, "deep")
    assert result["settings"]["effective"] == {
        "freeze_window_active": True,
        "high_risk": True,
    }
    assert result["level"] == "medium"  # explicit service flag, not the freeze
    assert len(result["settings_conflicts"]) == 2
    assert captured[0]["settings_conflicts"] == result["settings_conflicts"]
    assert (
        "team:notification-service.freeze_window_active" in captured[0]["evidence_keys"]
    )
    assert (
        "catalog:notification-service.freeze_window_active"
        not in captured[0]["evidence_keys"]
    )
    rendered = advisor.render(result)
    assert "Setting conflict" in rendered and "takes precedence" in rendered
    assert change == original


@pytest.mark.parametrize(
    "settings", [None, [], True, {"extra": True}, {"high_risk": 1}]
)
def test_malformed_settings_are_usage_errors(settings):
    with pytest.raises(ValueError, match="settings"):
        advisor.assess({**CHANGE, "settings": settings}, "fast")


def test_routes_and_rule_prose_never_make_execution_decisions():
    assert advisor.RULES["routes"] == {
        "low": "routine-review",
        "medium": "focused-review",
        "high": "priority-review",
    }
    for comment in advisor.RULES["system1"]["comments"].values():
        assert not system2._DECISION.search(comment["text"])


def test_no_foreign_incident_is_retrieved_only_for_its_change_type():
    result = advisor.assess(CHANGE, "fast")
    assert all(
        i["service"] == CHANGE["service"] or len(i["matched_terms"]) >= 2
        for i in result["incident_context"]
    )
