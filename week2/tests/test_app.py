"""Task 18: same guarded workflow, projected trace and host-owned identities."""

from uuid import uuid4
from types import SimpleNamespace
import os
from pathlib import Path
import subprocess
import sys
import pytest

from week2 import app
from week2.memory import MemoryStore


def test_import_respects_deployment_temp_directory(tmp_path):
    cache = tmp_path / "gradio"
    result = subprocess.run(
        [sys.executable, "-c", "from week2 import app; import os, sys; "
         "assert os.environ['GRADIO_TEMP_DIR'] == sys.argv[1]", str(cache)],
        cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, "GRADIO_TEMP_DIR": str(cache)},
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('args,environment,host,port', [
    ([],None,'127.0.0.1',7862),
    (['--host','0.0.0.0'],'8080','0.0.0.0',8080),
    (['--port','8123'],'invalid','127.0.0.1',8123),
])
def test_startup_binding_contract(monkeypatch,args,environment,host,port):
    calls=[]
    monkeypatch.delenv('PORT',raising=False)
    if environment is not None:monkeypatch.setenv('PORT',environment)
    monkeypatch.setattr(app,'build_app',lambda **kwargs:SimpleNamespace(launch=lambda **kw:calls.append(kw)))
    app.main(args)
    assert len(calls)==1 and calls[0]['server_name']==host and calls[0]['server_port']==port
    assert calls[0]['share'] is False and calls[0]['mcp_server'] is False
    assert calls[0]['enable_monitoring'] is False and calls[0]['show_error'] is False
    assert app.os.environ['FORWARDED_ALLOW_IPS']==''


@pytest.mark.parametrize('value',['0','-1','65536','text',''])
def test_invalid_runtime_port_exits_before_launch(monkeypatch,value):
    monkeypatch.setenv('PORT',value)
    monkeypatch.setattr(app,'build_app',lambda **kw:pytest.fail('invalid configuration reached the server'))
    with pytest.raises(SystemExit) as error:app.main([])
    assert error.value.code==2


def test_memory_write_callback_and_distinct_session_recall(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    a, b = uuid4().hex, uuid4().hex
    answer, summary, trace = app.ui_reply(
        "Remember that checkout-service is always high-risk for our team.", [], "Local evidence only", a, memory_store=store)
    assert trace["status"] == "memory_saved" and trace["session_id"] == a
    assert trace["langsmith"]["status"] == "not_configured"
    answer, summary, trace = app.ui_reply("What services depend on checkout-service?", [], "Local evidence only", b, memory_store=store)
    assert trace["session_id"] == b and trace["memory"]["status"] == "recalled"
    assert "Remembered high-risk flag: **true**" in summary
    assert "get_dependency_graph(checkout-service)" in summary
    assert trace["events"][1]["transport"] == "mcp-stdio"


def test_projection_does_not_export_arbitrary_state():
    assert app.project_trace({"status": "ok", "raw_sdk": object(), "prompt": "private", "environment": "secret"}) == {"status": "ok"}


def test_build_has_langsmith_trace_view_and_no_team_selector(tmp_path):
    demo = app.build_app(memory_store=MemoryStore(tmp_path / "memory.sqlite3"))
    components = demo.config["components"]
    assert any(c["props"].get("elem_id") == "langsmith-trace" for c in components)
    assert not any(c["type"] == "json" and c["props"].get("visible", True) for c in components)
    assert not any(c["props"].get("label") in {"Team", "Database path"} for c in components)
    assert not any("Groq assessment" in str(c["props"].get("choices", [])) for c in components)
    assert any("Local evidence only" in str(c["props"].get("value", ""))
               and c["type"] == "markdown" for c in components)
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
