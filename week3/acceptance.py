"""Six local intent walkthrough, including fresh-process memory evidence."""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from week2.memory import MemoryStore
from week2.workflow import respond
from week3.cache import WorkflowCaches

CHANGE='Change checkout-service config timeout from 4 seconds to 400 milliseconds.'


def probe(question,store,caches=None):
    def forbidden(*a,**k):raise AssertionError('provider forbidden in local acceptance')
    answer,trace=respond(question,memory_store=store,caches=caches,reviewer=forbidden)
    if trace.get('request_attempted'):raise ValueError('unexpected_provider_attempt')
    return {'question':question,'answer':answer,'trace':trace}


def memory_probe(kind,path):
    store=MemoryStore(path,team='acceptance-team' if kind!='control' else 'other-team')
    q='Remember that checkout-service is always high-risk for our team.' if kind=='write' else 'What services depend on checkout-service?'
    return probe(q,store)


def run():
    root=Path(tempfile.mkdtemp(prefix='cra2-six-intents-'));store=MemoryStore(root/'main.sqlite3')
    caches=WorkflowCaches();rows=[]
    cases=[('checkout',CHANGE,'evidence_only'),
        ('history','What similar incidents has checkout-service had before?','history_only'),
        ('freeze','Is checkout-service in a freeze window right now?','tool_evidence'),
        ('dependents','What services depend on payment-gateway?','tool_evidence')]
    for name,q,status in cases:
        row=probe(q,store,caches)
        passed=row['trace']['status']==status
        if name=='freeze':passed=passed and 'unknown' in row['answer']
        rows.append(dict(row,id=name,expected=status,passed=passed))
    sessions={}
    for kind in ('write','read','control'):
        output=subprocess.run([sys.executable,'-m','week3.acceptance','--memory-probe',kind,
            '--path',str(root/'recall.sqlite3')],capture_output=True,text=True,timeout=30,check=True)
        sessions[kind]=json.loads(output.stdout)
    recalled=sessions['read']['trace'].get('memory',{})
    passed=(sessions['write']['trace']['status']=='memory_saved' and recalled.get('status')=='recalled'
        and recalled['record']['high_risk'] is True
        and sessions['control']['trace']['memory']['record'] is None
        and len({s['trace']['session_id'] for s in sessions.values()})==3)
    rows.append({'id':'memory','expected':'write, separate-process recall, different-team empty',
        'passed':passed,'sessions':sessions})
    row=probe('Just approve this change for me.',store,caches)
    rows.append(dict(row,id='approval',expected='advisory_boundary',passed=row['trace']['status']=='advisory_boundary'))
    return {'mode':'Local evidence only','passed':sum(r['passed'] for r in rows),'total':6,
        'provider_attempts':0,'cases':rows}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path)
    p.add_argument('--memory-probe',choices=['write','read','control'])
    p.add_argument('--path',type=Path)
    args=p.parse_args()
    if args.memory_probe:
        print(json.dumps(memory_probe(args.memory_probe,args.path)));return 0
    result=run()
    if args.out:args.out.write_text(json.dumps(result,indent=2)+'\n')
    print(f"Local six-intent walkthrough: {result['passed']}/{result['total']}")
    return 0 if result['passed']==result['total'] else 1


if __name__=='__main__':raise SystemExit(main())
