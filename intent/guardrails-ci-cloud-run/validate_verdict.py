"""Reproduce the manifest-bound access verdict; no external evidence is loaded."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def validate(manifest, verdict):
    assert verdict['option_id'] in {o['id'] for o in manifest['options']}
    assert verdict['level'] in {'possible', 'suitable', 'preferred'}
    evidence = {e['id']: e for e in manifest['evidence']}
    assert verdict['evidence_ids'] and set(verdict['evidence_ids']) <= evidence.keys()
    if verdict['level'] == 'preferred':
        top = manifest['priority_order'][0]
        assert any(evidence[e]['type'] == 'COMPARATIVE' and top in evidence[e]['criteria']
                   for e in verdict['evidence_ids']), 'No comparative evidence on the top priority'
        assert not any(r['status'] == 'UNKNOWN' for r in manifest['requirements'])
        assert verdict['winner_established'] is True
    else:
        assert verdict['winner_established'] is False
        assert 'winner not established' in verdict['rationale']
        assert verdict['separating_test']


if __name__ == '__main__':
    stem = sys.argv[1] if len(sys.argv)>1 else 'iap-access-v2'
    assert stem in {'iap-access','iap-access-v2'}
    raw = (ROOT/(stem+'.pinned.json')).read_bytes()
    manifest = json.loads(raw)
    assert raw == (json.dumps(manifest,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n').encode()
    digest = hashlib.sha256(raw).hexdigest()
    verdict = json.loads((ROOT/(stem+'.judge.json')).read_text())
    validate(manifest,verdict)
    # Detection proof: the same capability evidence cannot validate 'preferred'.
    try:
        validate(manifest,dict(verdict,level='preferred',winner_established=True))
    except AssertionError:
        pass
    else:
        raise AssertionError('Harness accepted unsupported preferred level')
    record_path = ROOT/(stem+'.record.json')
    if record_path.exists():
        record = json.loads(record_path.read_text())
        assert record['sha256'] == digest and record['verdict'] == verdict, 'Pin a new revision for material changes'
    else:
        previous = None
        basis = 'Initial pinned decision after user refined access to invited Google accounts.'
        if stem=='iap-access-v2':
            prior = json.loads((ROOT/'iap-access.record.json').read_text())
            old = json.loads((ROOT/'iap-access.pinned.json').read_text())
            assert manifest['options']==old['options'] and manifest['evidence']==old['evidence']
            assert manifest['requirements']!=old['requirements']
            previous = prior['sha256']
            basis = 'User added owner acceptance and explicit approval before invitations or access grants.'
        record = {'sha256':digest,'delta':'requirement','previous':previous,
            'delta_basis':basis,
            'verdict':verdict}
        record_path.write_text(json.dumps(record,indent=2)+'\n')
    print(f"⟦ verdict · sha256={digest} · level={verdict['level']} · delta={record['delta']} ⟧")
