"""LangSmith replaces the PIN layer; raw snapshots remain server-side only."""

import asyncio
from inspect import unwrap
from types import SimpleNamespace

import gradio as gr
from gradio.state_holder import SessionState
from starlette.requests import Request

from week2 import app
from week2.memory import MemoryStore


def snapshot(turn=1, mode="Local evidence only"):
    return {"turn": turn, "review_mode": mode, "status": "help", "question": "private-question-canary",
            "response_details": "private-details-canary", "events": [], "retrieved": [],
            "provider_used": False, "request_attempted": False, "transport": "browser",
            "langsmith": {"status": "not_configured"}}


def callback(demo, name):
    return next(unwrap(fn.fn) for fn in demo.fns.values() if fn.fn and fn.fn.__name__ == name)


def test_tabs_use_langsmith_without_pin_or_browser_execution_details(tmp_path):
    demo = app.build_app(memory_store=MemoryStore(tmp_path / "memory.sqlite3"))
    try:
        components = demo.config["components"]
        tabs = [c["props"]["label"] for c in components if c["type"] == "tabitem"]
        assert tabs == ["Change Risk Advisor", "LangSmith"]
        assert not any(c["props"].get("label") in {"Demo PIN", "Execution details", "Agent trace"} for c in components)
        assert not any(c["type"] == "json" and c["props"].get("visible", True) for c in components)
        assert any(c["props"].get("elem_id") == "langsmith-trace" for c in components)
        assert next(c for c in components if c["type"] == "radio")["props"]["value"] == "Local evidence only"
        reply_fn = next(fn for fn in demo.fns.values() if fn.fn and fn.fn.__name__ == "reply")
        assert reply_fn.inputs[-1].stateful and reply_fn.inputs[-1].value == []
    finally:
        demo.close()


def test_selected_turn_renders_only_private_link_and_original_mode():
    trace = snapshot(2, "Groq assessment")
    trace["langsmith"] = {"status": "submitted", "url": "https://smith.langchain.com/o/test/r/test"}
    text, timer = app.langsmith_view(2, [snapshot(), trace])
    assert "Turn #2" in text and "Groq assessment" in text
    assert "Open this trace in LangSmith" in text and timer["active"] is False
    assert "canary" not in text
    trace["langsmith"]["url"] = "javascript:alert(1)"
    assert "javascript" not in app.langsmith_view(2, [trace])[0]


def test_history_callbacks_keep_lifecycle_without_exposing_snapshots(tmp_path, monkeypatch):
    demo = app.build_app(memory_store=MemoryStore(tmp_path / "memory.sqlite3"))
    try:
        traces = [snapshot(), snapshot(2, "Groq assessment")]
        monkeypatch.setattr(app, "guarded_ui_reply", lambda *_a, **_k: ("Short answer", "", traces[1]))
        request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
        result = callback(demo, "reply")("Question", [], "Groq assessment", "test", traces[:1], request)
        assert result[0] == "Short answer" and result[2] == traces
        assert "canary" not in str(result[1])
        assert result[3]["value"] == 2 and "Groq assessment" in result[3]["choices"][-1][0]
        undo = callback(demo, "undo_trace")(traces)
        assert undo[1] == traces[:1] and "Turn #1" in undo[0]
        cleared = callback(demo, "reset_trace")()
        assert cleared[1] == [] and cleared[2]["choices"] == []
        assert len(cleared[-1]) == 32  # Clear starts a fresh LangSmith thread.
    finally:
        demo.close()


def test_gradio_serialization_keeps_snapshots_server_side_and_ignores_forged_state(tmp_path, monkeypatch):
    demo = app.build_app(memory_store=MemoryStore(tmp_path / "memory.sqlite3"))
    try:
        record = snapshot()
        monkeypatch.setattr(app, "guarded_ui_reply", lambda *_a, **_k: ("Short answer", "", record))
        reply_fn = next(fn for fn in demo.fns.values() if fn.fn and fn.fn.__name__ == "reply")
        state = SessionState(demo)
        request = gr.Request(Request({"type": "http", "client": ("127.0.0.1", 9999)}))
        result = asyncio.run(demo.process_api(reply_fn, ["Question", [], "Local evidence only", "forged", [record]], state=state, request=request))
        assert "Short answer" in str(result["data"])
        assert "canary" not in str(result["data"])
        trace_state = reply_fn.inputs[-1]
        assert trace_state.stateful and state[trace_state._id] == [record]
        assert result["data"][reply_fn.outputs.index(trace_state)] is None
    finally:
        demo.close()
