"""Only sanitized experimental metrics enter the existing admin trace surface."""

import json
from types import SimpleNamespace

from week2 import app
from week2.presentation import project_execution


def test_execution_projection_excludes_raw_state_and_invalid_metrics():
    trace = app.project_trace({"status": "evidence_only", "execution": {
        "mode": "sac", "status": "completed", "action_count": 3,
        "completed_actions": 3, "model_action_count": 0, "state_bytes": 821,
        "compaction_count": 3, "context_tokens": 12345,
        "peak_context_bytes": True, "reduction_ms": float("nan"),
        "raw_state": {"objective": "private-state-canary"},
        "owner": "private-owner-canary", "action_history": ["private-history-canary"],
    }})
    serialized = json.dumps(trace)
    assert "private-" not in serialized
    assert trace["execution"]["context_tokens"] is None
    assert "peak_context_bytes" not in trace["execution"]
    assert "reduction_ms" not in trace["execution"]
    summary = app.trace_summary(trace)
    assert "sac" in summary and "Actions: 3" in summary and "State bytes: 821" in summary
    assert "12345" not in summary


def test_unrecognized_execution_labels_are_never_rendered():
    for value in (None, [], {"mode": "<script>private</script>", "status": "completed"},
                  {"mode": "sac", "status": "private-diagnostic"}):
        assert project_execution(value) == {}
        assert "private" not in app.trace_summary({"execution": value})


def test_context_mode_cli_configures_existing_app_without_exposing_selector(monkeypatch):
    captured = []
    # Register restoration before main intentionally sets the process setting.
    monkeypatch.setenv("CRA2_CONTEXT_MODE", "full")
    monkeypatch.setattr("sys.argv", ["cra2-week2", "--context-mode", "sac", "--port", "7869"])
    monkeypatch.setattr(app, "build_app", lambda **_kwargs: SimpleNamespace(
        launch=lambda **kwargs: captured.append(kwargs)))
    app.main()
    assert app.os.environ["CRA2_CONTEXT_MODE"] == "sac"
    assert captured[0]["server_name"] == "127.0.0.1"
    assert captured[0]["server_port"] == 7869 and captured[0]["share"] is False
