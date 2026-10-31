"""Reproduce offline dependency-query timings; no provider or live source."""
import time

IMPORT_STARTED=time.perf_counter()
import argparse
import json
import math
import platform
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from week2.workflow import respond
from week2.memory import MemoryStore
from week3.cache import WorkflowCaches, file_version


def percentile(values,q):
    return round(sorted(values)[max(0,math.ceil(len(values)*q)-1)],3)


def run(trials=30):
    if trials<30:raise ValueError('at_least_30_trials_required')
    query='What services depend on payment-gateway?'
    store=MemoryStore(Path(tempfile.mkdtemp(prefix='cra2-benchmark-'))/'memory.sqlite3')
    def invoke(cache):
        start=time.perf_counter();_,trace=respond(query,memory_store=store,caches=cache)
        elapsed=(time.perf_counter()-start)*1000
        if trace['status']!='tool_evidence' or trace.get('request_attempted'):
            raise ValueError('benchmark_contract_failed')
        return {'elapsed_ms':round(elapsed,3),'request_id':trace['request_id'],
            'actual_tool_results':sum(e['event']=='tool_result' for e in trace.get('events',[])),
            'cache':trace.get('cache',[]),'provider_attempted':False}
    imported_ms=(time.perf_counter()-IMPORT_STARTED)*1000
    first=invoke(None)
    expiry_clock=[0.0]
    caches={'disabled':None,'enabled_empty':WorkflowCaches(),
        'warm':WorkflowCaches(),'expired':WorkflowCaches(ttl=5,clock=lambda:expiry_clock[0])}
    warmup={name:invoke(caches[name]) for name in ('warm','expired')}
    rows={name:[] for name in caches}
    for i in range(trials):
        for name,cache in caches.items():
            if name=='enabled_empty':cache.clear()
            if name=='expired':expiry_clock[0]+=6
            rows[name].append(dict(invoke(cache),trial=i+1))
    summary={}
    for name,samples in rows.items():
        times=[r['elapsed_ms'] for r in samples]
        lookups=[e for r in samples for e in r['cache'] if e['layer']=='tool']
        summary[name]={'n':len(samples),'p50_ms':percentile(times,.5),'p95_ms':percentile(times,.95),
            'actual_tool_results':sum(r['actual_tool_results'] for r in samples),
            'hits':sum(e['outcome']=='hit' for e in lookups),'eligible_lookups':len(lookups)}
    base=summary['disabled']['p50_ms'];warm=summary['warm']['p50_ms']
    return {'completed_at_utc':datetime.now(timezone.utc).isoformat(),'query':query,
        'mode':'Local evidence only','environment':{'python':platform.python_version(),
            'system':platform.system(),'machine':platform.machine()},
        'versions':{p:file_version(p) for p in ('week2/workflow.py','week3/cache.py','week3/guardrails.py','week2/uv.lock')},
        'method':'Interleaved disabled/empty/warm/expired trials; imports and initial request separate; no outliers removed.',
        'module_import_ms':round(imported_ms,3),'first_request':first,'excluded_warmups':warmup,
        'summary':summary,'warm_p50_reduction_pct':round(100*(base-warm)/base,2),
        'samples':rows,'provider_attempts':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--trials',type=int,default=30)
    args=parser.parse_args()
    report=run(args.trials)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['summary'],indent=2))
    print('Warm p50 reduction:',report['warm_p50_reduction_pct'],'%')


if __name__=='__main__':main()
