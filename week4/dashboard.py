"""Session-only browser metrics. Never read owner audit or other transports."""
import json
import math
from pathlib import Path

from week1.responses import guard

EVIDENCE=Path(__file__).resolve().parents[1]/'docs/evidence'


def rate(n,d):
    return f'{100*n/d:.1f}% ({n}/{d})' if d else 'Not measured (0 eligible)'


def recorded_score(name):
    try:
        path=EVIDENCE/name
        if path.is_symlink() or path.stat().st_size>1024*1024:return None
        r=json.loads(path.read_text())
        if type(r['passed']) is not int or type(r['total']) is not int or not 0<=r['passed']<=r['total']<=10000:return None
        return f"{r['passed']}/{r['total']}"
    except (OSError,ValueError,KeyError,TypeError):return None


def dashboard_view(traces,unlocked):
    if unlocked is not True:return 'Admin is locked.'
    rows=[t for t in traces[-50:] if t.get('transport')=='browser']
    metrics=[t.get('mcp',{}) for t in rows]
    known=[m for m in metrics if m.get('status') in {'measured','not_accessed'}]
    attempts=sum(m.get('attempted') or 0 for m in known)
    failed=sum(m.get('failed') or 0 for m in known)
    unknown=sum(m.get('status') not in {'measured','not_accessed'} for m in metrics)
    rails=[e for t in rows for e in t.get('rails',[])]
    interventions=sum(e.get('outcome') in {'block','unavailable'} for e in rails)
    eligible=[t['memory'] for t in rows if t.get('memory',{}).get('status') in {'recalled','empty'}
        and any(s.get('stage')=='memory_read' for s in t.get('spans',[]))]
    applied=sum(m.get('effective_policy',{}).get('sources',{}).get('high_risk','').startswith('memory:')
        and m.get('effective_policy',{}).get('effective',{}).get('high_risk') is True for m in eligible)
    floors=sum(m.get('effective_policy',{}).get('effective',{}).get('high_risk') is True
        and not m.get('effective_policy',{}).get('sources',{}).get('high_risk','').startswith('memory:') for m in eligible)
    times=sorted(t['duration_ms'] for t in rows if type(t.get('duration_ms')) in (float,int))
    timing=(f"{times[max(0,math.ceil(len(times)*.5)-1)]:.1f} / {times[max(0,math.ceil(len(times)*.95)-1)]:.1f} ms (n={len(times)})"
        if times else 'Not measured (n=0)')
    lines=['## Run dashboard',f'Current browser session · latest {len(rows)} measured requests (maximum 50).',
        '| Metric | Observed value |','|---|---|',
        f'| Tool-call failure rate | {rate(failed,attempts)} |',
        f'| Actual tool invocations | {attempts} |',
        f'| Requests with unavailable tool accounting | {unknown} |',
        f'| Guardrail interventions / checks | {interventions}/{len(rails)} |',
        f"| Admission pauses | {sum(t.get('status')=='security_blocked' for t in rows)} |",
        f'| High-risk preferences applied / eligible reads | {rate(applied,len(eligible))} |',
        f'| Configured high-risk floors observed | {floors} |',
        f"| Actual model-request attempts | {sum(bool(t.get('request_attempted')) for t in rows)} |",
        f'| Workflow time p50 / p95 | {timing} |',
        '\n### Cache use','| Layer | Hits / eligible lookups |','|---|---|']
    for layer in ('query_embedding','retrieval','tool'):
        lookups=[e for t in rows for e in t.get('cache',[]) if e.get('layer')==layer]
        lines.append(f"| {layer.replace('_',' ')} | {rate(sum(e['outcome']=='hit' for e in lookups),len(lookups))} |")
    lines+=['\n### Recorded local scorecard',
        'Original baseline: **'+(recorded_score('week4-task-28-baseline.json') or 'not recorded')+
        '** → application fix: **'+(recorded_score('week4-task-30-after.json') or 'not recorded')+'**.',
        'Corrected reserved-label validation: **'+(recorded_score('week4-task-30-reserved-v2.json') or 'not recorded')+'**; the original 2/4 report is retained.',
        'Synthetic contract cases only. Live model quality remains unmeasured.',
        '\nCache hits are reuse, not new tool calls. Zero eligible calls has no failure rate. Workflow time excludes admission screening and browser rendering.',
        f'Other or unlabeled transports excluded: {len(traces[-50:])-len(rows)}. Owner audit records are not read.']
    result='\n\n'.join(lines[:2])+'\n\n'+'\n'.join(lines[2:])
    guard(result)
    return result
