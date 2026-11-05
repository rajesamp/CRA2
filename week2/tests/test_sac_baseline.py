"""The P0 report is reproducible and labels unavailable evidence honestly."""

from copy import deepcopy
import json

from scripts import benchmark_sac
import pytest


def test_baseline_refuses_experiment_environment_before_any_work(monkeypatch):
    monkeypatch.setenv("CRA2_CONTEXT_MODE", "sac")
    monkeypatch.setattr(benchmark_sac.workflow, "respond",
                        lambda *_a, **_k: pytest.fail("Mode mismatch must fail before work"))
    with pytest.raises(ValueError, match="Unset CRA2_CONTEXT_MODE"):
        benchmark_sac.run_benchmark(repeat=1)


def test_offline_baseline_pairs_are_repeatable_and_usage_is_not_invented(monkeypatch):
    # Source collection is separately integration-tested by the actual CLI run;
    # keep this test independent of the user's current git checkout metadata.
    monkeypatch.setattr(benchmark_sac, "source_metadata", lambda: {"git_sha": "test"})
    report = benchmark_sac.run_benchmark(repeat=2)
    assert report["dataset"]["case_count"] == 7
    assert report["summary"]["sample_count"] == 28
    assert report["summary"]["pair_count"] == 14
    assert report["summary"]["failure_count"] == 0
    assert report["failures"] == []
    assert report["comparison"] == "baseline-observer-off-vs-on"
    assert report["configuration"]["provider"] is None
    assert report["configuration"]["model"] is None
    assert report["summary"]["compaction_overhead_ms"] is None
    assert all(s["input_tokens"] is None and s["output_tokens"] is None
               and s["provider_requests"] == 0 for s in report["samples"])
    assert any(s["tool_calls"] == 2 for s in report["samples"])
    assert len(report["dataset"]["sha256"]) == 64


def test_percentiles_use_documented_nearest_rank():
    assert benchmark_sac.percentile([5, 1, 3, 2, 4], .5) == 3
    assert benchmark_sac.percentile([5, 1, 3, 2, 4], .95) == 5


def test_report_binds_loaded_policy_catalog_and_rules_without_exporting_them(monkeypatch):
    monkeypatch.setattr(benchmark_sac, "source_metadata", lambda: {"git_sha": "unchanged"})
    baseline = benchmark_sac.run_benchmark(repeat=1)
    original = baseline["configuration"]["loaded_inputs_sha256"]
    assert set(original) == {"team_settings", "catalog", "rules"}
    assert all(len(value) == 64 for value in original.values())

    authorities = {
        "TEAM_SETTINGS": deepcopy(benchmark_sac.chat.TEAM_SETTINGS),
        "CATALOG": deepcopy(benchmark_sac.chat.CATALOG),
        "RULES": deepcopy(benchmark_sac.chat.RULES),
    }
    private_team = "private-team-not-for-telemetry"
    authorities["TEAM_SETTINGS"]["team"] = private_team
    service = authorities["CATALOG"]["checkout-service"]
    service["high_risk"] = not service.get("high_risk", False)
    authorities["RULES"]["system2"]["weight"] += 0.01
    for name, value in authorities.items():
        monkeypatch.setattr(benchmark_sac.chat, name, value)
    changed = benchmark_sac.run_benchmark(repeat=1)
    assert changed["source"] == baseline["source"]
    assert changed["dataset"] == baseline["dataset"]
    assert changed["summary"]["failure_count"] == 0
    assert all(changed["configuration"]["loaded_inputs_sha256"][name] != digest
               for name, digest in original.items())
    assert changed["configuration_sha256"] != baseline["configuration_sha256"]
    assert private_team not in json.dumps(changed)
