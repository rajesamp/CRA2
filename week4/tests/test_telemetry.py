"""Correlation, actual attempt accounting, private metadata and bounded failure."""
import json
import sqlite3
import pytest

from week2.workflow import respond
from week2.memory import MemoryStore
from week2.mcp_client import call_tools
from week3.cache import WorkflowCaches
from week4.telemetry import TelemetryStore, TelemetryUnavailable

Q='What services depend on payment-gateway?'


def test_correlated_hit_without_fabricated_call_and_private_storage(tmp_path):
    store=MemoryStore(tmp_path/'m.sqlite3');c=WorkflowCaches();sink=TelemetryStore(tmp_path/'telemetry'/'records.sqlite3')
    first=respond(Q,memory_store=store,caches=c,telemetry_store=sink)[1]
    hit=respond(Q,memory_store=store,caches=c,telemetry_store=sink)[1]
    assert first['mcp']['attempted']==1 and hit['mcp']['attempted']==0
    assert hit['telemetry_status']=='recorded'
    assert first['request_id']!=hit['request_id']
    assert all(e['request_id']==hit['request_id'] for key in ('spans','events','rails','cache') for e in hit[key])
    assert {'memory_read','tools','compose','output_guard','rail_input','rail_output','cache_tool'} <= {e['stage'] for e in hit['spans']}
    with sqlite3.connect(sink.path) as db:records=[json.loads(r[0]) for r in db.execute('SELECT body FROM requests')]
    assert len(records)==2 and Q not in str(records)
    assert all('question' not in r and 'memory' not in r and 'answer' not in r for r in records)
    assert sink.path.stat().st_mode & 0o777==0o600


def test_actual_mcp_deadline_is_operation_failure_not_fabricated_invocation(tmp_path):
    async def timeout(calls):return await call_tools(calls,timeout=.000001)
    answer,t=respond(Q,tool_runner=timeout,memory_store=MemoryStore(tmp_path/'m.sqlite3'))
    assert t['status']=='tools_unavailable' and t['events'][0]['code']=='timeout'
    assert t['mcp']=={'attempted':0,'failed':0,'status':'measured'}
    assert all(s['request_id']==t['request_id'] for s in t['spans'])


def test_full_metadata_store_preserves_rows_and_fails_safely(tmp_path):
    sink=TelemetryStore(tmp_path/'telemetry'/'records.sqlite3',max_rows=1)
    store=MemoryStore(tmp_path/'m.sqlite3')
    assert respond('What is this app?',memory_store=store,telemetry_store=sink)[1]['telemetry_status']=='recorded'
    answer,t=respond('What is this app?',memory_store=store,telemetry_store=sink)
    assert t['status']=='telemetry_unavailable' and 'No risk indication' in answer
    with sqlite3.connect(sink.path) as db:assert db.execute('SELECT count(*) FROM requests').fetchone()[0]==1


def test_insecure_or_symlink_store_rejected(tmp_path):
    path=tmp_path/'public';path.mkdir(mode=0o755)
    sink=TelemetryStore(path/'records.sqlite3')
    trace={'request_id':'a'*32,'transport':'cli','status':'help','duration_ms':1}
    with pytest.raises(TelemetryUnavailable):sink.write(trace)
    private=tmp_path/'private';private.mkdir(mode=0o700)
    link=private/'records.sqlite3';link.symlink_to(path/'file')
    with pytest.raises(TelemetryUnavailable):TelemetryStore(link).write(trace)
