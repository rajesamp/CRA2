"""Exercise writes across fresh processes against a persistent GCS contract fixture."""

import concurrent.futures
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from week2.cloud_storage import CloudStores, StorageClient, StorageSettings
from week2.memory import MemoryUnavailable
from week2.owner_audit import AuditUnavailable


STATE = 'state-synthetic'
AUDIT = 'audit-synthetic'
OWNER = 'iap:' + 'a' * 64
OTHER = 'iap:' + 'b' * 64
SERVICE = 'checkout-service'
DAY = 86400
ROOT = Path(__file__).resolve().parents[2]


class ObjectFixture:
    """SQLite-backed contract service. Cloud enforcement has a separate gate."""

    def __init__(self, path, now=0):
        self.path, self.now = path, now
        self.locked = True
        self.fail_upload_bucket = None
        self.missing_bucket = None
        self.before_write = None
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS objects (generation INTEGER PRIMARY KEY AUTOINCREMENT, '
                       'bucket TEXT, name TEXT, body BLOB, created INTEGER, UNIQUE(bucket, name))')

    def bucket(self, bucket):
        metadata = {'iamConfiguration': {'uniformBucketLevelAccess': {'enabled': True},
                                         'publicAccessPrevention': 'enforced'},
                    'softDeletePolicy': {'retentionDurationSeconds': '0'},
                    'lifecycle': {'rule': [{'action': {'type': 'Delete'}, 'condition': {
                        'age': 30 if bucket == AUDIT else 7,
                        'matchesPrefix': ['audit/v1/' if bucket == AUDIT else 'telemetry/v1/']}}]}}
        if bucket == AUDIT:
            metadata['retentionPolicy'] = {'isLocked': self.locked, 'retentionPeriod': str(30 * DAY)}
        return metadata

    def handle(self, req):
        if req.url.host == 'metadata.google.internal':
            assert req.headers['Metadata-Flavor'] == 'Google'
            assert 'Authorization' not in req.headers
            return httpx.Response(200, headers={'Metadata-Flavor': 'Google'},
                                  json={'access_token': 'synthetic-fixture-token', 'expires_in': 3600})
        assert req.url.host == 'storage.googleapis.com'
        assert req.headers['Authorization'] == 'Bearer synthetic-fixture-token'
        parts = req.url.path.split('/b/', 1)[1].split('/o', 1)
        bucket = parts[0]
        if bucket == self.missing_bucket:
            return httpx.Response(404)
        if len(parts) == 1:
            return httpx.Response(200, json=self.bucket(bucket))
        name = req.url.params['name'] if req.method == 'POST' else parts[1].removeprefix('/')
        if req.method == 'POST' and self.before_write is not None:
            self.before_write(bucket, name)
        with sqlite3.connect(self.path) as db:
            if req.method == 'POST':
                db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT generation, body, created FROM objects WHERE bucket=? AND name=?',
                             (bucket, name)).fetchone()
            if req.method == 'GET':
                if old is None:
                    return httpx.Response(404)
                if req.url.params.get('alt') == 'media':
                    if req.url.params['ifGenerationMatch'] != str(old[0]):
                        return httpx.Response(412)
                    return httpx.Response(200, content=old[1])
                return httpx.Response(200, json={'generation': str(old[0])})
            if (bucket == AUDIT and old and self.now - old[2] < 30 * DAY
                    and (req.method == 'DELETE' or req.url.params.get('ifGenerationMatch') == str(old[0]))):
                return httpx.Response(403, json={'error': 'retentionPolicyNotMet'})
            assert req.method == 'POST' and req.url.params['uploadType'] == 'media'
            if bucket == self.fail_upload_bucket:
                return httpx.Response(503)
            if int(req.url.params['ifGenerationMatch']) != (old[0] if old else 0):
                return httpx.Response(412)
            if old:
                assert bucket == STATE and name.startswith('preferences/v1/')
                db.execute('DELETE FROM objects WHERE generation=?', (old[0],))
            db.execute('INSERT INTO objects (bucket,name,body,created) VALUES (?,?,?,?)',
                       (bucket, name, req.content, self.now))
            return httpx.Response(200, json={'name': name})

    def stores(self):
        return CloudStores(StorageSettings(STATE, AUDIT), client=StorageClient(
            httpx.Client(transport=httpx.MockTransport(self.handle))))

    def count(self, bucket, prefix):
        with sqlite3.connect(self.path) as db:
            return db.execute('SELECT count(*) FROM objects WHERE bucket=? AND name LIKE ?',
                              (bucket, prefix + '%')).fetchone()[0]

    def cleanup(self, now):
        with sqlite3.connect(self.path) as db:
            for bucket in (STATE, AUDIT):
                rule = self.bucket(bucket)['lifecycle']['rule'][0]['condition']
                db.execute('DELETE FROM objects WHERE bucket=? AND name LIKE ? AND created<=?',
                           (bucket, rule['matchesPrefix'][0] + '%', now - rule['age'] * DAY))


def test_preferences_and_audit_survive_application_process_restart(tmp_path):
    path = str(tmp_path / 'objects.sqlite3')
    probe = '''
import json, runpy, sys
m = runpy.run_path('week2/tests/test_cloud_storage.py')
f = m['ObjectFixture'](sys.argv[1]); s = f.stores(); memory = s.memory_for(m['OWNER'])
if sys.argv[2] == 'write':
    record = memory.write(m['SERVICE'], high_risk=True)
    s.audit.append('synthetic question', 'a'*64, 'out_of_scope', {'action': 'ALLOW'})
else:
    record = memory.read(m['SERVICE'])
print(json.dumps([record, f.count(m['AUDIT'], 'audit/v1/'), s.memory_for(m['OTHER']).read(m['SERVICE'])]))
'''
    write, read = [json.loads(subprocess.check_output([sys.executable, '-c', probe, path, mode],
                                                    cwd=ROOT, text=True, timeout=45))
                   for mode in ('write', 'read')]
    assert write == read and read[0]['high_risk'] is True
    assert read[1:] == [3, None]
    with sqlite3.connect(path) as db:
        audit = [json.loads(b) for b, in db.execute('SELECT body FROM objects WHERE bucket=?', (AUDIT,))]
    assert {x['kind'] for x in audit} == {'memory_write_requested', 'memory_write_committed', 'out_of_scope'}
    assert all('question' not in x and 'freeze_notes' not in x for x in audit)


def test_concurrent_independent_updates_merge_after_generation_conflict(tmp_path):
    import threading
    fixture = ObjectFixture(tmp_path / 'objects.sqlite3')
    barrier = threading.Barrier(2)
    seen = threading.local()

    def synchronize(bucket, name):
        if name.endswith('/' + SERVICE + '.json') and not getattr(seen, 'first', False):
            seen.first = True
            barrier.wait(timeout=10)

    fixture.before_write = synchronize
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        a = pool.submit(fixture.stores().memory_for(OWNER).write, SERVICE, high_risk=True)
        b = pool.submit(fixture.stores().memory_for(OWNER).write, SERVICE, freeze_notes='Check with owner')
        a.result(timeout=15)
        b.result(timeout=15)
    record = fixture.stores().memory_for(OWNER).read(SERVICE)
    assert (record['high_risk'], record['freeze_notes']) == (True, 'Check with owner')
    assert fixture.count(AUDIT, 'audit/v1/') == 4


def test_retention_expires_metadata_without_terminal_row_cap(tmp_path):
    fixture = ObjectFixture(tmp_path / 'objects.sqlite3')
    stores = fixture.stores()
    stores.memory_for(OWNER).write(SERVICE, high_risk=True)
    for n in range(2002):
        stores.telemetry.write({'request_id': f'{n:032x}', 'transport': 'browser',
                                'status': 'evidence_only', 'duration_ms': 1, 'question': 'not telemetry'})
    assert fixture.count(STATE, 'telemetry/v1/') == 2002
    fixture.cleanup(7 * DAY - 1)
    assert fixture.count(STATE, 'telemetry/v1/') == 2002
    fixture.cleanup(7 * DAY)
    assert fixture.count(STATE, 'telemetry/v1/') == 0
    fixture.cleanup(30 * DAY - 1)
    assert fixture.count(AUDIT, 'audit/v1/') == 2
    fixture.cleanup(30 * DAY)
    assert fixture.count(AUDIT, 'audit/v1/') == 0
    assert stores.memory_for(OWNER).read(SERVICE)['high_risk'] is True


def test_wrong_retention_and_audit_failure_block_mutation(tmp_path):
    fixture = ObjectFixture(tmp_path / 'objects.sqlite3')
    fixture.locked = False
    with pytest.raises(AuditUnavailable):
        fixture.stores().audit.ensure()
    assert fixture.count(STATE, 'preferences/v1/') == 0
    fixture.locked = True
    fixture.fail_upload_bucket = AUDIT
    with pytest.raises(MemoryUnavailable):
        fixture.stores().memory_for(OWNER).write(SERVICE, high_risk=True)
    memory = fixture.stores().memory_for(OWNER)
    assert memory.read(SERVICE) is None
    assert fixture.count(STATE, memory._name(SERVICE)) == 0


def test_missing_bucket_and_a_lifecycle_rule_for_preferences_do_not_pass(tmp_path):
    fixture = ObjectFixture(tmp_path / 'objects.sqlite3')
    fixture.missing_bucket = STATE
    with pytest.raises(MemoryUnavailable, match='^memory_unavailable$'):
        fixture.stores().memory_for(OWNER).read(SERVICE)
    fixture.missing_bucket = None
    metadata = fixture.bucket

    def wrong_policy(bucket):
        row = metadata(bucket)
        if bucket == STATE:
            row['lifecycle']['rule'][0]['condition']['matchesPrefix'] = ['preferences/v1/']
        return row

    fixture.bucket = wrong_policy
    with pytest.raises(AuditUnavailable, match='^audit_unavailable$'):
        fixture.stores().audit.ensure()
