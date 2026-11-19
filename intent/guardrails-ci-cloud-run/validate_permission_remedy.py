"""Reproduce the frozen permission-remedy verdict; authorization is separate."""
import hashlib
import json
from pathlib import Path

from validate_ingress_verdict import validate

ROOT = Path(__file__).resolve().parent
STEM = 'policy-permission-remedy-v1'

if __name__ == '__main__':
    raw = (ROOT / (STEM + '.pinned.json')).read_bytes()
    manifest = json.loads(raw)
    assert raw == (json.dumps(manifest, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=False) + '\n').encode()
    verdict = json.loads((ROOT / (STEM + '.judge.json')).read_text())
    record = json.loads((ROOT / (STEM + '.record.json')).read_text())
    assert record['sha256'] == hashlib.sha256(raw).hexdigest()
    assert record['verdict'] == verdict
    validate(manifest, verdict)
    try:
        validate(manifest, dict(verdict, level='preferred', winner_established=True))
    except AssertionError:
        pass
    else:
        raise AssertionError('Unsupported preference passed detection control')
    footer = (f"⟦ verdict · sha256={record['sha256']} · "
              f"level={verdict['level']} · delta={record['delta']} ⟧")
    assert record['footer'] == footer
    print(footer)
