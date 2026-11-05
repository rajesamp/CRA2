"""Explicit local fault injection; canonical data and owner records untouched."""
import argparse
import asyncio
import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

from week1 import retrieval,chat
from week2 import mcp_client,workflow
from week2.memory import MemoryStore
from week3.cache import WorkflowCaches
from week3.guardrails import LocalRails
from week4.telemetry import TelemetryStore

CHANGE='Change checkout-service config timeout from 4 seconds to 400 milliseconds.'


def run():
    root=Path(tempfile.mkdtemp(prefix='cra2-faults-'));rows=[]
    def probe(label,query,expected,**kwargs):
        answer,trace=workflow.respond(query,memory_store=kwargs.pop('memory_store',MemoryStore(root/(label+'.sqlite3'))),
            transport='evaluation',**kwargs)
        passed=trace['status']==expected and not trace.get('request_attempted') and not trace.get('assessment')
        row={'case':label,'expected':expected,'passed':passed,'answer':answer,'trace':trace}
        rows.append(row);return row
    params=mcp_client.server_parameters()
    slow='''import asyncio,time
from week2 import mcp_server as s
original=s.FUNCTIONS['check_system_health']
def slow(**kwargs):
    time.sleep(12)
    return original(**kwargs)
s.FUNCTIONS['check_system_health']=slow
asyncio.run(s.main())
'''
    async def deadline(calls):return await mcp_client.call_tools(calls,timeout=6)
    with patch.object(mcp_client,'server_parameters',lambda:params.model_copy(update={'args':['-c',slow]})):
        row=probe('health-invocation-timeout','Is checkout-service current health okay?','tools_unavailable',tool_runner=deadline)
    row['passed'] &= row['trace']['mcp']['attempted']==1 and row['trace']['mcp']['failed']==1
    probe('ambiguous-reference','Review this change.','needs_clarification')
    probe('no-matching-evidence',CHANGE,'insufficient_evidence',retriever=lambda *a,**k:[])
    hits=retrieval.search(CHANGE,chat.INDEX,limit=3,service='checkout-service')
    store=MemoryStore(root/'mutation.sqlite3')
    def mutate(*a,**k):store.write('checkout-service',high_risk=True);return hits
    row=probe('policy-changed-inflight',CHANGE,'context_changed',memory_store=store,retriever=mutate,caches=WorkflowCaches())
    row['passed'] &= row['trace']['mcp']['attempted']==2
    changed_policy=dict(workflow.chat.TEAM_SETTINGS,team='different-team')
    with patch.object(workflow,'load_settings',lambda *a:changed_policy):
        row=probe('configured-team-changed','What services depend on checkout-service?','memory_unavailable',memory_store=store)
    row['passed'] &= row['trace']['mcp']['attempted']==0 and not row['trace'].get('memory',{}).get('record')
    rails=LocalRails()
    async def unavailable(*a,**k):raise RuntimeError('synthetic SDK failure')
    with patch.object(rails.engine,'check_async',unavailable):
        probe('required-rail-unavailable','What is this app?','guardrails_unavailable',guardrails=rails)
    sink=TelemetryStore(root/'telemetry'/'requests.sqlite3',max_rows=1)
    workflow.respond('What is this app?',telemetry_store=sink,transport='evaluation',memory_store=MemoryStore(root/'full.sqlite3'))
    row=probe('metadata-capacity',CHANGE,'telemetry_unavailable',telemetry_store=sink)
    with sqlite3.connect(sink.path) as db:row['retained_rows']=db.execute('SELECT count(*) FROM requests').fetchone()[0]
    row['passed'] &= row['retained_rows']==1
    caches=WorkflowCaches();version=['before'];actual=[]
    caches.tool_version=lambda:version[0]
    async def changed(calls):
        result=await mcp_client.call_tools(calls)
        actual.append(result['metrics']['attempted']);version[0]='after'
        return result
    with patch.object(workflow,'call_tools',changed):
        row=probe('source-version-changed-inflight','What services depend on payment-gateway?','tools_unavailable',caches=caches)
    row['actual_fault_probe_invocations']=sum(actual)
    row['passed'] &= sum(actual)==1 and not caches.tools.items
    probe('corpus-index-absent',CHANGE,'retrieval_unavailable',index_path=root/'missing-index.sqlite3')
    return {'mode':'local fault injection','passed':sum(bool(r['passed']) for r in rows),
        'total':len(rows),'provider_attempts':0,'cases':rows}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();report=run();args.out.write_text(json.dumps(report,indent=2)+'\n')
    print(f"Fault checks: {report['passed']}/{report['total']}; provider attempts: 0")
    return 0 if report['passed']==report['total'] else 1


if __name__=='__main__':raise SystemExit(main())
