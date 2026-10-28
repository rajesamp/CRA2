"""The demo gate controls trace projection, without pretending to authenticate."""

import asyncio
from inspect import unwrap
from types import SimpleNamespace

import pytest
import gradio as gr
from gradio.state_holder import SessionState
from starlette.requests import Request

from week2 import app
from week2.memory import MemoryStore


def snapshot(turn=1, mode="Local evidence only"):
    return {"turn": turn, "review_mode": mode, "status": "help", "question": "What is this app?",
            "response_details": "trace-only-canary", "events": [], "retrieved": [],
            "provider_used": False, "request_attempted": False}


def callback(demo, name):
    # ChatInterface wraps the synchronous callback in its asynchronous submit fn.
    return next(unwrap(fn.fn) for fn in demo.fns.values() if fn.fn and fn.fn.__name__ == name)


@pytest.mark.parametrize("pin", ["0000", "0427", "7139", "9999"])
def test_any_four_ascii_digits_unlock_without_saving_input(pin):
    traces = [snapshot()]
    unlocked, field, status, login, panel, summary, details, supporting, accordion, selector = app.unlock_admin(pin, traces)
    assert unlocked is True and field["value"] == ""
    assert status["value"] == "" and status["visible"] is False
    assert login["visible"] is False and panel["visible"] is True
    assert details == traces[0] and supporting == "trace-only-canary"
    assert selector["choices"] == [("Turn #1 · Local evidence only", 1)]
    assert pin not in str((status, summary, details, supporting, accordion, selector))


@pytest.mark.parametrize("pin", [None, 1234, "", "123", "12345", " 1234", "1234\n", "12a4", "１２３４", "١٢٣٤"])
def test_invalid_demo_input_keeps_trace_locked(pin):
    result = app.unlock_admin(pin, [snapshot()])
    assert result[0] is False and result[1]["value"] == ""
    assert result[3]["visible"] is True and result[4]["visible"] is False
    assert result[6] == {} and result[7] == "" and result[9]["choices"] == []
    assert "trace-only-canary" not in str(result)


def test_locked_selection_and_logout_never_project_saved_snapshots():
    traces = [snapshot(), snapshot(2, "Groq assessment")]
    for state in (False, None, 1, "true"):
        view = app.admin_trace_view(1, traces, state)
        assert view[1] == {} and view[2] == "" and view[4]["choices"] == []
        assert "trace-only-canary" not in str(view)
    view = app.admin_trace_view(1, traces, True)
    assert view[1] == traces[0] and "Local evidence only" in view[0]
    assert view[4]["choices"][-1] == ("Turn #2 · Groq assessment", 2)
    locked = app.lock_admin()
    assert locked[0] is False and locked[4]["visible"] is False
    assert "trace-only-canary" not in str(locked)
    assert len(traces) == 2


def test_tabs_start_locked_with_trace_controls_inside_admin(tmp_path):
    demo = app.build_app(memory_store=MemoryStore(tmp_path / "memory.sqlite3"))
    try:
        components = demo.config["components"]
        tabs = [c for c in components if c["type"] == "tabitem"]
        assert [c["props"]["label"] for c in tabs] == ["Change Risk Advisor", "Admin"]
        admin_group = next(c for c in components if c["props"].get("elem_id") == "admin-trace-controls")
        assert admin_group["props"]["visible"] is False
        pin = next(c for c in components if c["props"].get("label") == "Demo PIN")
        assert pin["type"] == "textbox" and pin["props"]["type"] == "password"
        assert not pin["props"].get("value")
        assert not any("not owner authentication" in str(c["props"].get("value", "")) for c in components)
        status = next(c for c in components if c["props"].get("elem_id") == "admin-status")
        assert status["props"]["visible"] is False
        reply_fn = next(fn for fn in demo.fns.values() if fn.fn and fn.fn.__name__ == "reply")
        assert reply_fn.inputs[-1].stateful and reply_fn.inputs[-1].value is False
        # The only output holding locked snapshots must be server-side State.
        assert any(output.stateful and output.value == [] for output in reply_fn.outputs)
    finally:
        demo.close()


def test_all_history_callbacks_respect_locked_view_and_keep_lifecycle(tmp_path, monkeypatch):
    demo = app.build_app(memory_store=MemoryStore(tmp_path / "memory.sqlite3"))
    try:
        traces = [snapshot(), snapshot(2, "Groq assessment")]
        monkeypatch.setattr(app, "guarded_ui_reply", lambda *_a, **_k: ("Short answer", "", traces[1]))
        request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
        locked = callback(demo, "reply")("Question", [], "Groq assessment", "test", traces[:1], False, request)
        assert locked[0] == "Short answer" and locked[2] == {} and locked[3] == ""
        assert locked[5] == traces and locked[6]["choices"] == []
        unlocked = callback(demo, "reply")("Question", [], "Groq assessment", "test", traces[:1], True, request)
        assert unlocked[2] == traces[1] and "Turn #2" in unlocked[4]["label"]
        undo = callback(demo, "undo_trace")(traces, False)
        assert undo[1] == {} and undo[4] == traces[:1] and undo[5]["choices"] == []
        undo = callback(demo, "undo_trace")(traces, True)
        assert undo[1] == traces[0] and undo[4] == traces[:1]
        cleared = callback(demo, "reset_trace")(True)
        assert cleared[1] == {} and cleared[4] == [] and cleared[5]["choices"] == []
    finally:
        demo.close()


def test_gradio_serialization_keeps_locked_snapshots_on_server_and_ignores_forged_state(tmp_path, monkeypatch):
    demo = app.build_app(memory_store=MemoryStore(tmp_path / "memory.sqlite3"))
    try:
        record = snapshot()
        monkeypatch.setattr(app, "guarded_ui_reply", lambda *_a, **_k: ("Short answer", "", record))
        reply_fn = next(fn for fn in demo.fns.values() if fn.fn and fn.fn.__name__ == "reply")
        state = SessionState(demo)
        request = gr.Request(Request({"type": "http", "client": ("127.0.0.1", 9999)}))
        # Client-supplied history/unlock values must not override server State.
        inputs = ["Question", [], "Local evidence only", "forged", [record], True]
        result = asyncio.run(demo.process_api(reply_fn, inputs, state=state, request=request))
        assert "Short answer" in str(result["data"])
        assert "trace-only-canary" not in str(result["data"])
        trace_output = reply_fn.inputs[-2]
        assert trace_output.stateful and trace_output in reply_fn.outputs
        assert state[trace_output._id] == [record]
        assert result["data"][reply_fn.outputs.index(trace_output)] is None
        assert state[reply_fn.inputs[-1]._id] is False
    finally:
        demo.close()
