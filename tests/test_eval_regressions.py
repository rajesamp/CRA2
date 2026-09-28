"""Regression tests for repeat coverage, actionable gates, and honest accounting."""

import copy
import importlib.util
from pathlib import Path

import pytest

from cra2.advisor import assess

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "eval_regression_runner", ROOT / "scripts" / "run_evals.py"
)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


@pytest.fixture
def sample(monkeypatch):
    case = next(case for case in runner.CASES if case["id"] == "CHG-02")
    monkeypatch.setattr(runner, "CASES", [case])
    return case, assess(case["change"], "fast")


def feed(monkeypatch, results):
    iterator = iter(copy.deepcopy(results))
    monkeypatch.setattr(runner, "assess", lambda *_args: next(iterator))


def provider_result(base, *, usage=(100, 20), failed=False, cached=False, request=True):
    result = copy.deepcopy(base)
    result.update(
        system2_attempted=True,
        system2_request_attempted=request,
        system2_cache_hit=cached,
        path="system1" if failed else "system2",
    )
    result["system2"] = None if failed else {"tokens": usage}
    result["system2_failure_usage"] = {"tokens": usage} if failed else None
    return result


def test_later_repeat_regression_affects_metrics_and_gate(monkeypatch, sample):
    _, good = sample
    bad = copy.deepcopy(good)
    bad.update(level="high", route="priority-review")
    feed(monkeypatch, [good, bad])
    rows, summary = runner.run("fast", 2)
    assert rows[0]["totals"] == [10, 4]
    assert summary["Mean rubric score (all assessments)"] == "7.00 / 10"
    assert summary["Level correct (all assessments)"] == "1/2"
    assert summary["Route correct (all assessments)"] == "1/2"
    assert rows[0]["same"] is False
    assert runner.gate_failures(rows) == ["CHG-02 repeat 2: score 4 < 10"]


def test_every_provider_outcome_is_counted_without_rebilling_cache(monkeypatch, sample):
    _, base = sample
    feed(
        monkeypatch,
        [
            provider_result(base),
            provider_result(base, usage=(0, 0), cached=True, request=False),
            provider_result(base, usage=(50, 5), failed=True),
            provider_result(base, usage=None, failed=True, request=False),
        ],
    )
    rows, summary = runner.run("deep", 4, 1, 2)
    assert (
        summary["System 2 requested / SDK attempts / cache hits / failed"]
        == "4 / 2 / 1 / 2"
    )
    assert summary["SDK attempts with known / missing token usage"] == "2 / 0"
    assert summary["Observed token-cost subtotal"].startswith("0.000200 USD")
    assert summary["Estimated token cost per 1,000 assessments"].startswith(
        "0.050000 USD"
    )
    assert len(runner.gate_failures(rows)) == 2


def test_missing_usage_prevents_complete_cost_estimate(monkeypatch, sample):
    _, base = sample
    feed(monkeypatch, [provider_result(base), provider_result(base, usage=None)])
    _, summary = runner.run("deep", 2, 1, 2)
    assert summary["SDK attempts with known / missing token usage"] == "1 / 1"
    assert summary["Observed token-cost subtotal"].startswith("0.000140 USD (1/2")
    assert summary["Estimated token cost per 1,000 assessments"].startswith("unknown:")


def test_absent_prices_are_unknown_and_explicit_zero_prices_are_valid(
    monkeypatch, sample
):
    _, base = sample
    feed(monkeypatch, [provider_result(base)])
    _, summary = runner.run("deep", 1)
    assert summary["Observed token-cost subtotal"].startswith("unknown:")
    feed(monkeypatch, [provider_result(base)])
    _, summary = runner.run("deep", 1, 0, 0)
    assert summary["Observed token-cost subtotal"].startswith("0.000000 USD")


def test_fast_run_has_no_provider_cost_sample_or_single_run_repeatability(sample):
    rows, summary = runner.run("fast", 1)
    assert rows[0]["same"] is None
    assert (
        summary["Same decision context across 1 repeats"] == "not assessed: one repeat"
    )
    assert summary["Estimated token cost per 1,000 assessments"].startswith(
        "not applicable:"
    )
    assert runner.pct([], 0.95) is None
    assert runner.pct(list(range(1, 21)), 0.95) == 19


@pytest.mark.parametrize("repeat", [0, -1, True, 1.5])
def test_invalid_repeat_rejected_before_assessment(repeat):
    with pytest.raises(ValueError, match="positive integer"):
        runner.run("fast", repeat)


@pytest.mark.parametrize(
    "price_in, price_out",
    [(1, None), (None, 1), (-1, 1), (1, float("inf")), (float("nan"), 1)],
)
def test_invalid_or_partial_prices_rejected(price_in, price_out):
    with pytest.raises(ValueError):
        runner.run("fast", 1, price_in, price_out)


def test_main_returns_failure_and_writes_report(monkeypatch, sample, tmp_path):
    _, good = sample
    bad = copy.deepcopy(good)
    bad.update(level="high", route="priority-review")
    feed(monkeypatch, [good, bad])
    out = tmp_path / "nested" / "evidence.md"
    assert runner.main(["--mode", "fast", "--repeat", "2", "--out", str(out)]) == 1
    text = out.read_text()
    assert "Quality gate | FAIL" in text and "CHG-02 repeat 2" in text


def test_repeatability_gate_rejects_single_repeat_without_running(monkeypatch):
    monkeypatch.setattr(
        runner,
        "assess",
        lambda *_args: pytest.fail("should reject options before assessment"),
    )
    with pytest.raises(SystemExit) as exc:
        runner.main(["--require-repeatable"])
    assert exc.value.code == 2


def test_scorer_rejects_unknown_citations_and_duplicate_tags(sample):
    case, result = sample
    for comment in result["comments"]:
        comment["evidence"] = ["CX-NOT-GIVEN"]
        comment["tag"] = "rollback"
    marks = runner.mark(case, result)
    assert marks["cite"] == 0 and marks["format"] == 0


def test_no_usage_sample_never_becomes_a_zero_cost_subtotal(monkeypatch, sample):
    _, base = sample
    feed(monkeypatch, [provider_result(base, usage=None, failed=True)])
    _, summary = runner.run("deep", 1, 1, 2)
    assert summary["Observed token-cost subtotal"].startswith("unknown:")
    assert summary["Estimated token cost per 1,000 assessments"].startswith("unknown:")


def test_clarification_scores_zero_and_fails_even_with_zero_threshold(
    monkeypatch, sample
):
    _, result = sample
    result.update(
        status="needs_clarification",
        level=None,
        score=None,
        route=None,
        comments=[],
        questions=["Which service does this change affect?"],
        freeze=None,
        settings=None,
        settings_conflicts=[],
        path="clarification",
    )
    feed(monkeypatch, [result])
    rows, summary = runner.run("fast", 1)
    assert rows[0]["totals"] == [0]
    assert summary["Assessed / needs clarification"] == "0 / 1"
    assert summary["Level correct (all assessments)"] == "0/1"
    assert runner.gate_failures(rows, min_score=0) == [
        "CHG-02 repeat 1: assessment needs clarification"
    ]
    report = runner.report("fast", 1, rows, summary)
    assert "needs_clarification" in report


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "needs_clarification"),
        ("questions", ["Confirm the current freeze window?"]),
        ("freeze", {"status": "unconfirmed", "reported_active": True, "evidence": []}),
        ("settings", {"team": "other-team", "effective": {"high_risk": True}}),
        (
            "settings_conflicts",
            [
                {
                    "field": "high_risk",
                    "requested": False,
                    "effective": True,
                    "source": "team:auth-service.high_risk",
                }
            ],
        ),
    ],
)
def test_repeatability_includes_review_context(monkeypatch, sample, field, value):
    _, first = sample
    second = copy.deepcopy(first)
    if field == "settings":
        second[field]["team"] = value["team"]
        second[field]["effective"].update(value["effective"])
    else:
        second[field] = value
    feed(monkeypatch, [first, second])
    rows, _ = runner.run("fast", 2)
    assert rows[0]["same"] is False
    assert "CHG-02: repeatability requirement unmet" in runner.gate_failures(
        rows, min_score=0, require_repeatable=True
    )


def test_review_routes_are_attention_levels_not_approval_decisions():
    assert {case["expected"]["route"] for case in runner.CASES} == {
        "routine-review",
        "focused-review",
        "priority-review",
    }
    for case in runner.CASES:
        result = assess(case["change"], "fast")
        assert result["status"] == "assessed"
        assert result["route"] == case["expected"]["route"]


@pytest.mark.parametrize(
    "case_id,expected_level", [("CHG-04", "medium"), ("CHG-08", "low")]
)
def test_freeze_cases_request_verification_without_forcing_high(
    case_id, expected_level
):
    case = next(case for case in runner.CASES if case["id"] == case_id)
    result = assess(case["change"], "fast")
    assert result["level"] == expected_level
    assert result["freeze"]["status"] == "unconfirmed"
    assert result["freeze"]["reported_active"] is True
    assert result["questions"]
    assert case["expected"]["level"] == expected_level


def test_team_policy_change_changes_report_fingerprint(monkeypatch, sample):
    _, before = runner.run("fast", 1)
    policy = copy.deepcopy(runner.TEAM_SETTINGS)
    policy["team"] = "another-team"
    monkeypatch.setattr(runner, "TEAM_SETTINGS", policy)
    _, after = runner.run("fast", 1)
    assert before["Team settings SHA256"] != after["Team settings SHA256"]
    assert before["Rules SHA256"] == after["Rules SHA256"]
    assert before["Catalog SHA256"] == after["Catalog SHA256"]
    assert len(after["Team settings SHA256"]) == 64


def test_report_rejects_known_key_used_as_model(monkeypatch, sample):
    sentinel = "gsk_fake_eval_sentinel_12345"
    rows, summary = runner.run("fast", 1)
    monkeypatch.setenv("GROQ_API_KEY", sentinel)
    monkeypatch.setattr(runner.config, "MODEL", sentinel)
    with pytest.raises(ValueError, match="Configured credentials") as exc:
        runner.report("fast", 1, rows, summary)
    assert sentinel not in str(exc.value)


def test_main_rejects_credential_output_path_without_writing(
    monkeypatch, sample, tmp_path, capsys
):
    sentinel = "gsk_fake_eval_path_12345"
    monkeypatch.setenv("GROQ_API_KEY", sentinel)
    target = tmp_path / sentinel / "report.md"
    with pytest.raises(SystemExit) as exc:
        runner.main(["--mode", "fast", "--out", str(target)])
    captured = capsys.readouterr()
    assert exc.value.code == 2
    assert sentinel not in captured.out + captured.err
    assert not target.parent.exists()


def test_main_rejects_credential_summary_without_writing(
    monkeypatch, sample, tmp_path, capsys
):
    sentinel = "gsk_fake_eval_summary_12345"
    rows, summary = runner.run("fast", 1)
    summary["extra"] = sentinel
    monkeypatch.setenv("GROQ_API_KEY", sentinel)
    monkeypatch.setattr(runner, "run", lambda *_args: (rows, summary))
    target = tmp_path / "report.md"
    with pytest.raises(SystemExit) as exc:
        runner.main(["--mode", "fast", "--out", str(target)])
    captured = capsys.readouterr()
    assert exc.value.code == 2
    assert sentinel not in captured.out + captured.err
    assert not target.exists()
