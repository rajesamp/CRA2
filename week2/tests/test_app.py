"""Task 18: same guarded workflow, projected trace and host-owned identities."""

from uuid import uuid4

from week2 import app
from week2.memory import MemoryStore


def test_memory_write_callback_and_distinct_session_recall(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    a, b = uuid4().hex, uuid4().hex
    answer, summary, trace = app.ui_reply(
        "Remember that checkout-service is always high-risk for our team.", [], "Local evidence only", a, memory_store=store)
    assert trace["status"] == "memory_saved" and trace["session_id"] == a
    answer, summary, trace = app.ui_reply("What services depend on checkout-service?", [], "Local evidence only", b, memory_store=store)
    assert trace["session_id"] == b and trace["memory"]["status"] == "recalled"
    assert "Remembered high-risk flag: **true**" in summary
    assert "get_dependency_graph(checkout-service)" in summary
    assert trace["events"][1]["transport"] == "mcp-stdio"


def test_projection_does_not_export_arbitrary_state():
    assert app.project_trace({"status": "ok", "raw_sdk": object(), "prompt": "private", "environment": "secret"}) == {"status": "ok"}


def test_build_has_collapsed_operational_trace_and_no_team_selector(tmp_path):
    demo = app.build_app(memory_store=MemoryStore(tmp_path / "memory.sqlite3"))
    components = demo.config["components"]
    accordion = next(c for c in components if c["type"] == "accordion" and c["props"].get("label") == "Agent trace")
    assert accordion["props"]["open"] is False
    assert not any(c["props"].get("label") in {"Team", "Database path"} for c in components)
    assert any(c["type"] == "state" for c in components)
    assert demo.analytics_enabled is False
    demo.close()


def test_unavailable_memory_produces_protected_trace(tmp_path):
    path = tmp_path / "bad.sqlite3"
    path.write_text("corrupt")
    answer, summary, trace = app.ui_reply("What services depend on checkout-service?", [], "Local evidence only", uuid4().hex,
        memory_store=MemoryStore(path))
    assert trace["status"] == "memory_unavailable"
    assert "corrupt" not in answer and str(path) not in str(trace)
    assert "No tool result" in summary
