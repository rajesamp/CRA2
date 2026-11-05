"""TTL, mutation, bounds, isolation, real RPC avoidance and single-flight."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from time import sleep

import anyio
import pytest

from week3.cache import ExactCache, WorkflowCaches, identity
from week2 import workflow
from week2.memory import MemoryStore
from week2.tests.test_workflow import HIT, CHANGE


def test_absolute_expiry_copy_and_byte_eviction():
    now=[0.0];c=ExactCache(ttl=5,entries=2,byte_limit=40,clock=lambda:now[0])
    c.put('a',{'x':1});v,_=c.get('a');v['x']=9
    assert c.get('a')[0]=={'x':1}
    now[0]=4;assert c.get('a')
    now[0]=5;assert c.get('a') is None
    c.put('a',{'x':1});c.put('b',{'x':2});c.put('c',{'x':3})
    assert c.get('a') is None and c.bytes<=40 and len(c.items)<=2
    assert not c.put('huge','x'*100)


def test_failures_and_inflight_source_mutation_not_cached():
    c=ExactCache()
    def bad():raise ValueError('failed')
    with pytest.raises(ValueError):c.load('a',bad)
    with pytest.raises(ValueError):c.load('a',lambda:{'x':1},lambda:False)
    assert c.get('a') is None and not c.pending


def test_synchronous_singleflight():
    c=ExactCache();calls=[]
    def compute():calls.append(1);sleep(.02);return [1]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _:c.load('same',compute),range(4)))
    assert len(calls)==1 and [e['outcome'] for _,e in results].count('miss')==1


def test_async_singleflight_and_error_cleanup():
    async def run():
        c=ExactCache();calls=[];results=[]
        async def compute():calls.append(1);await anyio.sleep(.02);return [1]
        async def worker():results.append(await c.aload('same',compute))
        async with anyio.create_task_group() as group:
            for _ in range(4):group.start_soon(worker)
        assert len(calls)==1 and len(results)==4 and not c.pending
    anyio.run(run)


def test_actual_graph_hit_expiry_and_team_policy_isolation(tmp_path):
    now=[0.0];c=WorkflowCaches(ttl=5,clock=lambda:now[0]);q='What services depend on payment-gateway?'
    store=MemoryStore(tmp_path/'m.sqlite3',team='team-a')
    a,t1=workflow.respond(q,caches=c,memory_store=store)
    a,t2=workflow.respond(q,caches=c,memory_store=store)
    assert t1['status']==t2['status']=='tool_evidence'
    assert any(e['event']=='tool_result' for e in t1['events'])
    assert not any(e['event']=='tool_result' for e in t2['events'])
    assert t2['cache'][0]['outcome']=='hit' and t1['request_id']!=t2['request_id']
    other=MemoryStore(store.path,team='team-b')
    assert workflow.respond(q,caches=c,memory_store=other)[1]['cache'][0]['outcome']=='miss'
    store.write('payment-gateway',high_risk=True)
    assert workflow.respond(q,caches=c,memory_store=store)[1]['cache'][0]['outcome']=='miss'
    now[0]=6
    assert workflow.respond(q,caches=c,memory_store=store)[1]['cache'][0]['outcome']=='miss'


def test_exact_numeric_queries_have_different_identity():
    assert identity([CHANGE])!=identity([CHANGE.replace('400 milliseconds','4 milliseconds')])


def test_policy_mutation_during_work_discards_response(tmp_path):
    store=MemoryStore(tmp_path/'m.sqlite3');c=WorkflowCaches()
    def retrieve(*a,**k):
        store.write('checkout-service',high_risk=True)
        return [deepcopy(HIT)]
    answer,trace=workflow.respond(CHANGE,caches=c,memory_store=store,retriever=retrieve)
    assert trace['status']=='context_changed' and 'No risk indication' in answer


def test_tool_source_mutation_invalidates_entries(tmp_path,monkeypatch):
    from week2 import tools
    from week2.contracts import NAMES
    source=tmp_path/'source.json';source.write_text('v1')
    monkeypatch.setattr(tools,'CATALOG_PATH',source)
    version=[WorkflowCaches.tool_version()];c=WorkflowCaches();calls=[]
    from week2.tests.test_workflow import HIT
    # Validate a real result before swapping the fingerprint-only source.
    from cra2.config import DATA_DIR
    monkeypatch.setattr(tools,'CATALOG_PATH',DATA_DIR/'checkout_system.json')
    result=tools.get_dependency_graph('payment-gateway')
    monkeypatch.setattr(tools,'CATALOG_PATH',source)
    async def runner(batch):
        calls.extend(batch)
        return {'status':'ok','outputs':{NAMES[1]:result},'events':[]}
    async def run():
        batch=[(NAMES[1],{'service_name':'payment-gateway'})]
        await c.call_tools(batch,scope='a',runner=runner)
        await c.call_tools(batch,scope='a',runner=runner)
        source.write_text('v2')
        out=await c.call_tools(batch,scope='a',runner=runner)
        assert out['cache_events'][0]['outcome']=='miss'
    anyio.run(run)
    assert len(calls)==2 and c.tool_version()!=version[0]


def test_real_retrieval_embedding_reuse_and_index_mutation(tmp_path):
    import shutil,sqlite3
    from week1.chat import INDEX
    copied=tmp_path/'index.sqlite3';shutil.copyfile(INDEX,copied)
    c=WorkflowCaches();events=[]
    opts=dict(limit=3,service='checkout-service',scope='team-a',events=events)
    first=c.retrieve(CHANGE,copied,**opts)
    second=c.retrieve(CHANGE,copied,**opts)
    assert first==second and events[-1]['outcome']=='hit'
    c.retrieval.clear()
    c.retrieve(CHANGE,copied,**opts)
    assert any(e['layer']=='query_embedding' and e['outcome']=='hit' for e in events)
    c.retrieve(CHANGE.replace('400 milliseconds','4 milliseconds'),copied,**opts)
    assert events[-2]['layer']=='query_embedding' and events[-2]['outcome']=='miss'
    with sqlite3.connect(copied) as db:db.execute("UPDATE chunks SET text=text||' mutated' WHERE chunk_id=(SELECT MIN(chunk_id) FROM chunks)")
    with pytest.raises(ValueError):c.retrieve(CHANGE,copied,**opts)
