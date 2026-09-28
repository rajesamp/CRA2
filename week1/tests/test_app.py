"""Offline UI construction and launch-policy regressions; no server or tunnel."""

import sys
from secrets import token_hex

import pytest

from cra2 import system2
from week1 import app


@pytest.fixture(autouse=True)
def isolate_credentials_and_network(monkeypatch):
    monkeypatch.delenv("CRA2_ENV_FILE", raising=False)
    monkeypatch.delenv("CRA2_UI_USER", raising=False)
    monkeypatch.delenv("CRA2_UI_PASSWORD", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", token_hex(24))
    monkeypatch.setenv("GRADIO_ANALYTICS_ENABLED", "False")
    monkeypatch.setattr(
        system2, "assess", lambda *_a, **_k: pytest.fail("no live provider in UI tests")
    )
    monkeypatch.setattr(
        system2, "client", lambda: pytest.fail("no SDK client in UI tests")
    )
    monkeypatch.setattr(
        app.gr.Blocks,
        "launch",
        lambda *_a, **_k: pytest.fail("no actual server or sharing tunnel in UI tests"),
    )


@pytest.fixture
def launch_probe(monkeypatch, tmp_path):
    root = tmp_path / "project"
    here = root / "week1"
    here.mkdir(parents=True)
    index = here / "index.sqlite3"
    index.touch()
    calls = {"launch": [], "index": []}

    class StubApp:
        def launch(self, **kwargs):
            calls["launch"].append(kwargs)

    monkeypatch.setattr(app, "HERE", here)
    monkeypatch.setattr(app, "INDEX", index)
    monkeypatch.setattr(app, "build_app", lambda: StubApp())
    monkeypatch.setattr(app, "build_index", lambda *args: calls["index"].append(args))
    monkeypatch.setattr(sys, "argv", ["week1.app"])
    return calls, root, here, index


def test_default_launch_is_local_without_sharing_or_persistent_history(launch_probe):
    calls, root, _, _ = launch_probe
    app.main()
    assert not calls["index"]
    assert len(calls["launch"]) == 1
    launch = calls["launch"][0]
    assert launch["server_name"] == "127.0.0.1"
    assert launch["server_port"] == 7860
    assert launch["share"] is False and launch["auth"] is None
    assert launch["show_error"] is False and launch["inbrowser"] is False
    assert launch["enable_monitoring"] is False
    assert launch["run_history"] is False and launch["mcp_server"] is False
    assert str(root) in launch["blocked_paths"]


@pytest.mark.parametrize("present", [None, "CRA2_UI_USER", "CRA2_UI_PASSWORD"])
def test_share_requires_both_auth_fields_before_startup(
    monkeypatch, launch_probe, present
):
    calls, _, _, _ = launch_probe
    if present:
        monkeypatch.setenv(present, token_hex(24))
    monkeypatch.setattr(sys, "argv", ["week1.app", "--share", "--reindex"])
    with pytest.raises(SystemExit) as exc:
        app.main()
    assert exc.value.code == 2
    assert not calls["index"] and not calls["launch"]


def test_explicit_share_uses_auth_without_printing_credentials(
    monkeypatch, launch_probe, capsys
):
    calls, _, _, _ = launch_probe
    user, password = token_hex(24), token_hex(24)
    monkeypatch.setenv("CRA2_UI_USER", user)
    monkeypatch.setenv("CRA2_UI_PASSWORD", password)
    monkeypatch.setattr(sys, "argv", ["week1.app", "--share", "--port", "7999"])
    app.main()
    launch = calls["launch"][0]
    assert launch["share"] is True and launch["auth"] == (user, password)
    assert launch["server_name"] == "127.0.0.1" and launch["server_port"] == 7999
    captured = capsys.readouterr()
    assert user not in captured.out + captured.err
    assert password not in captured.out + captured.err


def test_credentials_alone_do_not_enable_sharing(monkeypatch, launch_probe):
    calls, _, _, _ = launch_probe
    monkeypatch.setenv("CRA2_UI_USER", token_hex(24))
    monkeypatch.setenv("CRA2_UI_PASSWORD", token_hex(24))
    app.main()
    assert calls["launch"][0]["share"] is False


def test_selected_external_dotenv_is_blocked_without_reading_it(
    monkeypatch, launch_probe, tmp_path
):
    calls, root, _, _ = launch_probe
    # This path does not exist: startup needs its identity, never its contents.
    selected = tmp_path / "external-secrets" / ".env.local"
    monkeypatch.setenv("CRA2_ENV_FILE", str(selected))
    app.main()
    assert not selected.exists()
    blocked = calls["launch"][0]["blocked_paths"]
    assert str(root) in blocked and str(selected.resolve()) in blocked


@pytest.mark.parametrize("reason", ["missing", "reindex"])
def test_missing_or_explicitly_refreshed_index_is_built_before_launch(
    monkeypatch, launch_probe, reason
):
    calls, _, here, index = launch_probe
    if reason == "missing":
        monkeypatch.setattr(app, "INDEX", index.with_name("not-yet-created.sqlite3"))
    else:
        monkeypatch.setattr(sys, "argv", ["week1.app", "--reindex"])
    app.main()
    assert calls["index"] == [(here / "corpus", app.INDEX)]
    assert len(calls["launch"]) == 1


def test_ui_errors_do_not_expose_exception_or_fake_credential(monkeypatch):
    sentinel = token_hex(24)
    monkeypatch.setenv("GROQ_API_KEY", sentinel)

    def fail(*_args):
        raise RuntimeError("Provider request failed with credential " + sentinel)

    monkeypatch.setattr(app, "respond", fail)
    answer, trace = app.ui_response("Review checkout-service.", [], "Groq assessment")
    assert sentinel not in answer + str(trace)
    assert "RuntimeError" not in answer and "Provider request failed" not in answer
    assert trace == {"status": "unavailable", "retrieved": []}
    assert "advisory only" in answer and "human decision" in answer


def test_ui_preserves_checked_answer_and_trace(monkeypatch):
    expected = ("Checked advisory.", {"status": "evidence_only", "retrieved": []})
    calls = []

    def respond(*args):
        calls.append(args)
        return expected

    monkeypatch.setattr(app, "respond", respond)
    history = [
        {"role": "user", "content": [{"type": "text", "text": "checkout-service"}]}
    ]
    assert (
        app.ui_response("Timeout 4 to 400.", history, "Local evidence only") == expected
    )
    assert calls == [("Timeout 4 to 400.", history, "Local evidence only")]


def test_actual_gradio_app_builds_with_six_examples_and_private_assessment_api(
    monkeypatch,
):
    original = app.gr.ChatInterface
    options = []

    def capture_interface(*args, **kwargs):
        options.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(app.gr, "ChatInterface", capture_interface)
    demo = app.build_app()
    assert demo.analytics_enabled is False
    interface = options[0]
    assert interface["save_history"] is False
    assert interface["cache_examples"] is False
    assert interface["flagging_mode"] == "never"
    assert interface["api_visibility"] == "private"
    assert interface["examples"] == [
        [question, "Groq assessment"] for question in app.EXAMPLES
    ]
    assert len(app.EXAMPLES) == 6
    components = demo.config["components"]
    assert any(component["type"] == "chatbot" for component in components)
    assert any(
        component["type"] == "textbox"
        and component["props"].get("label") == "Top 3 retrieved chunks and status"
        and component["props"].get("interactive") is False
        for component in components
    )
    assert any(
        component["type"] == "radio"
        and component["props"]["value"] == "Groq assessment"
        for component in components
    )
    assessment = [
        dependency
        for dependency in demo.config["dependencies"]
        if dependency.get("api_name") == "ui_response"
    ]
    assert len(assessment) == 1 and assessment[0]["api_visibility"] == "private"


def test_evidence_display_uses_plain_json_text(monkeypatch):
    import json

    monkeypatch.setattr(
        app,
        "ui_response",
        lambda *args: ("Advisory", {"status": "assessed", "retrieved": []}),
    )
    answer, display = app.ui_response_display("change", [], "Local evidence only")
    assert answer == "Advisory"
    assert json.loads(display) == {"status": "assessed", "retrieved": []}
