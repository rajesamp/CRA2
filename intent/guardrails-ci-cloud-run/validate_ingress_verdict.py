"""Validate immutable ingress assessments and reproduce harness-rendered footers."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def validate(manifest, verdict):
    evidence = {row['id']: row for row in manifest['evidence']}
    assert verdict['option_id'] in {row['id'] for row in manifest['options']}
    assert verdict['level'] in {'possible', 'suitable', 'preferred'}
    assert verdict['evidence_ids'] and set(verdict['evidence_ids']) <= evidence.keys()
    if verdict['level'] == 'preferred':
        assert any(evidence[key]['type'] == 'COMPARATIVE'
                   and manifest['priority_order'][0] in evidence[key]['criteria']
                   for key in verdict['evidence_ids'])
        # Conservative: no UNKNOWN requirement may support a preferred verdict.
        assert not any(row['status'] == 'UNKNOWN' for row in manifest['requirements'])
        assert verdict['winner_established'] is True
    else:
        assert verdict['winner_established'] is False
        assert 'winner not established' in verdict['rationale']
        assert verdict['separating_test']


def load(stem):
    raw = (ROOT / (stem + '.pinned.json')).read_bytes()
    manifest = json.loads(raw)
    assert raw == (json.dumps(manifest, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=False) + '\n').encode()
    verdict = json.loads((ROOT / (stem + '.judge.json')).read_text())
    record = json.loads((ROOT / (stem + '.record.json')).read_text())
    assert record['sha256'] == hashlib.sha256(raw).hexdigest()
    assert record['verdict'] == verdict
    validate(manifest, verdict)
    try:
        validate(manifest, dict(verdict, level='preferred', winner_established=True))
    except AssertionError:
        pass
    else:
        raise AssertionError('Detection control accepted an unsupported preference')
    return manifest, record


if __name__ == '__main__':
    first, previous = load('ingress-route-v1')
    current, record = load('ingress-route-v2')
    prior_access = json.loads((ROOT / 'iap-access-v2.record.json').read_text())
    assert previous['previous'] == prior_access['sha256']
    assert previous['delta'] == 'option added'
    assert record['previous'] == previous['sha256'] and record['delta'] == 'evidence'
    assert [o['id'] for o in first['options']] == [o['id'] for o in current['options']]
    assert current['evidence'][:-1] == first['evidence']
    assert current['evidence'][-1]['id'] == 'E7'
    footer = (f"⟦ verdict · sha256={record['sha256']} · "
              f"level={record['verdict']['level']} · delta={record['delta']} ⟧")
    assert record['footer'] == footer
    print(footer)
