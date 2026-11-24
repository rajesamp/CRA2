"""C4 uses the same signed endpoints, retention policies and conditional writes as CRA2."""
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3

import pytest

from week2.cloud_storage import StorageUnavailable
from week2.preference_journal import MutationStatus, journal_name
from week2.tests.test_cloud_storage import AUDIT, STATE, OWNER, OTHER, SERVICE, DAY, ObjectFixture
from week2.tests.test_iap import identity


def rows(fixture, bucket, prefix):
    with sqlite3.connect(fixture.path) as db:
        return [json.loads(body) for body, in db.execute(
            'SELECT body FROM objects WHERE bucket=? AND name LIKE ? ORDER BY generation',
            (bucket, prefix + '%'))]


def test_redelivery_after_later_edit_correlates_one_mutation(tmp_path):
    fixture = ObjectFixture(tmp_path / 'objects.db')
    store = fixture.stores().memory_for(OWNER)
    first, second = '1' * 32, '2' * 32
    store.write(SERVICE, high_risk=True, review_id=first)
    store.write(SERVICE, high_risk=False, review_id=second)
    before = store.read(SERVICE)
    fixture.stores().memory_for(OWNER).write(SERVICE, high_risk=True, review_id=first)
    assert store.read(SERVICE) == before
    audit = rows(fixture, AUDIT, 'audit/v1/')
    assert len(audit) == 4
    for review in (first, second):
        requested, committed = [row for row in audit if row['request_id'] == review]
        assert requested['kind'] == 'memory_write_requested'
        assert committed['kind'] == 'memory_write_committed'
        assert requested['mutation_id'] == committed['mutation_id']
        assert committed['generation'].isdigit()


def test_signed_recovery_withholds_report_when_telemetry_fails(tmp_path, identity, monkeypatch):
    from fastapi.testclient import TestClient
    from week2.cloud_app import create_app
    from week2.iap import IAPVerifier, IAPSettings
    from week2.tests.test_iap import token, protected, AUDIENCE, OWNER as EMAIL
    from week2.tests.test_incident_rollback import VALUES
    from week4.telemetry import TelemetryUnavailable

    _, keys = protected(identity)
    settings = IAPSettings(AUDIENCE, EMAIL)
    fixture = ObjectFixture(tmp_path / 'objects.db')
    stores = fixture.stores()
    def unavailable(*args):
        raise TelemetryUnavailable('offline')
    monkeypatch.setattr(stores.telemetry, 'write', unavailable)
    with TestClient(create_app(settings=settings, verifier=IAPVerifier(settings, keys=keys), stores=stores)) as client:
        response = client.post('/gradio_api/run/recovery',
            headers={'x-goog-iap-jwt-assertion': token(identity)},
            json={'session_hash': 'synthetic', 'data': [*VALUES, None]})
        assert response.status_code == 200
        report, _, activity = response.json()['data']
        assert 'review record could not be confirmed' in report
        assert 'Recovery evidence is incomplete' not in report
        assert 'Risk by category' not in report
        assert 'confirmation incomplete' in activity.lower()
        assert fixture.count(STATE, 'telemetry/v1/') == 0



@pytest.mark.parametrize('where,after,status', [
    ('request', True, 'memory_not_changed'),
    ('value', True, 'memory_unconfirmed'),
    ('result', False, 'memory_confirmation_incomplete'),
    ('result', True, 'memory_confirmation_incomplete'),
])
def test_lost_ack_restart_and_operator_repair(tmp_path, monkeypatch, where, after, status):
    from week2.reconcile_review import reconcile
    fixture = ObjectFixture(tmp_path / 'gcs.db')
    stores = fixture.stores()
    memory = stores.memory_for(OWNER)
    review, later = '3' * 32, '4' * 32
    original = stores.client.write
    def interrupt(bucket, name, row, generation='0'):
        target = (where == 'value' and name == memory._name(SERVICE)
                  or where == 'request' and name.endswith('-request.json')
                  or where == 'result' and name.endswith('-result.json'))
        if target:
            if after:
                original(bucket, name, row, generation)
            raise StorageUnavailable('lost_ack')
        return original(bucket, name, row, generation)
    monkeypatch.setattr(stores.client, 'write', interrupt)
    with pytest.raises(MutationStatus, match=status):
        memory.write(SERVICE, freeze_notes='private-note-canary', review_id=review)
    fresh = fixture.stores()
    memory = fresh.memory_for(OWNER)
    if where == 'request':
        assert memory.read(SERVICE) is None
        assert reconcile(fresh.settings, fresh.client, review) == 'unconfirmed'
        memory.write(SERVICE, freeze_notes='private-note-canary', review_id=review)
    else:
        assert memory.read(SERVICE)['freeze_notes'] == 'private-note-canary'
    # Same value, different logical edit. The earlier write must still be provable.
    memory.write(SERVICE, freeze_notes='private-note-canary', review_id=later)
    value, generation = fresh.client.read(STATE, memory._name(SERVICE))
    assert reconcile(fresh.settings, fresh.client, review) == 'committed'
    memory.write(SERVICE, freeze_notes='private-note-canary', review_id=review)
    assert fresh.client.read(STATE, memory._name(SERVICE)) == (value, generation)
    events = rows(fixture, AUDIT, 'audit/v1/')
    assert len(events) == 4 and 'private-note-canary' not in json.dumps(events)
    assert len({r['generation'] for r in events if r['outcome'] == 'committed'}) == 2


def test_duplicate_race_scope_and_payload_binding(tmp_path):
    fixture = ObjectFixture(tmp_path / 'concurrent.db')
    review = '5' * 32
    def deliver():
        try:
            fixture.stores().memory_for(OWNER).write(SERVICE, high_risk=True, review_id=review)
        except MutationStatus:
            pass  # An in-flight duplicate may see an unconfirmed acknowledgement.
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(lambda _: deliver(), range(4)))
    m = fixture.stores().memory_for(OWNER)
    m.write(SERVICE, high_risk=True, review_id=review)
    before = m.client.read(STATE, m._name(SERVICE))
    for who, service, flag in [(OTHER, SERVICE, True), (OWNER, SERVICE, False), (OWNER, 'inventory-service', True)]:
        with pytest.raises(MutationStatus, match='memory_replay_rejected'):
            fixture.stores().memory_for(who).write(service, high_risk=flag, review_id=review)
    assert m.client.read(STATE, m._name(SERVICE)) == before
    assert fixture.count(AUDIT, 'audit/v1/') == 2
    assert fixture.stores().memory_for(OTHER).read(SERVICE) is None


def test_reconciliation_rejects_different_create_only_row(tmp_path, monkeypatch):
    from week2.reconcile_review import reconcile
    fixture = ObjectFixture(tmp_path / 'mismatch.db')
    s = fixture.stores()
    m = s.memory_for(OWNER)
    original = s.client.write
    def collision(bucket, name, row, generation='0'):
        if name.endswith('-result.json'):
            original(bucket, name, dict(row, generation='9876'), generation)
        return original(bucket, name, row, generation)
    monkeypatch.setattr(s.client, 'write', collision)
    review = '6' * 32
    with pytest.raises(MutationStatus, match='memory_confirmation_incomplete'):
        m.write(SERVICE, high_risk=True, review_id=review)
    fresh = fixture.stores()
    original_repair = fresh.client.write
    def reject_overwrite(bucket, name, row, generation='0'):
        if bucket == AUDIT:
            pytest.fail('operator attempted to replace an existing locked audit event')
        original_repair(bucket, name, row, generation)
    monkeypatch.setattr(fresh.client, 'write', reject_overwrite)
    assert reconcile(fresh.settings, fresh.client, review) == 'unconfirmed'
    assert 'audit_confirmed' not in fresh.client.read(STATE, journal_name(review))[0]


def test_committed_preference_keeps_its_outcome_when_chat_telemetry_fails(tmp_path, monkeypatch):
    from week2.app import ui_reply
    from week2.reconcile_review import reconcile
    from week4.telemetry import TelemetryUnavailable
    f = ObjectFixture(tmp_path / 'chat.db')
    s = f.stores()
    m = s.memory_for(OWNER)
    review = '7' * 32
    def unavailable(*_):
        raise TelemetryUnavailable('offline')
    monkeypatch.setattr(s.telemetry, 'write', unavailable)
    answer, _, trace = ui_reply('Remember that checkout-service is high-risk.', [], 'Local evidence only',
                                'synthetic-session', memory_store=m, telemetry_store=s.telemetry, request_id=review)
    assert 'Preference saved. Confirmation record incomplete.' in answer
    assert trace['request_id'] == review and trace['telemetry_status'] == 'unavailable'
    value = s.client.read(STATE, m._name(SERVICE))
    assert value[0]['high_risk'] is True
    fresh = f.stores()
    assert reconcile(fresh.settings, fresh.client, review) == 'committed'
    repaired, = rows(f, STATE, 'telemetry/v1/')
    assert repaired['measurements'] == 'unavailable' and repaired['request_id'] == review
    assert fresh.client.read(STATE, m._name(SERVICE)) == value
    f.cleanup(7 * DAY)
    assert f.count(STATE, 'telemetry/v1/') == 0 and f.count(AUDIT, 'audit/v1/') == 2
    f.cleanup(30 * DAY - 1)
    assert f.count(AUDIT, 'audit/v1/') == 2
    f.cleanup(30 * DAY)
    assert f.count(AUDIT, 'audit/v1/') == 0
    assert fresh.client.read(STATE, m._name(SERVICE)) == value


def test_existing_v1_value_and_request_only_history_survive_upgrade(tmp_path):
    f = ObjectFixture(tmp_path / 'legacy.db')
    s = f.stores()
    m = s.memory_for(OWNER)
    value = m.updated(SERVICE, {}, {'high_risk': True, 'freeze_notes': 'legacy note'})
    s.client.write(STATE, m._name(SERVICE), value)
    s.audit.append(None, m.scope, 'memory_write_requested', {'service': SERVICE, 'outcome': 'requested'})
    assert m.read(SERVICE) == value
    m.write(SERVICE, high_risk=False)
    assert m.read(SERVICE)['freeze_notes'] == 'legacy note'
    old, requested, committed = rows(f, AUDIT, 'audit/v1/')
    assert 'request_id' not in old
    assert requested['request_id'] == committed['request_id']


@pytest.mark.parametrize('stage', ['admission', 'input', 'context', 'output', 'missing_input', 'ok', 'invalid'])
def test_actual_recovery_receipts_match_private_projection(tmp_path, identity, monkeypatch, stage):
    from fastapi.testclient import TestClient
    from week2.cloud_app import create_app
    from week2.iap import IAPVerifier, IAPSettings
    from week2.tests.test_iap import AUDIENCE, OWNER as EMAIL, token, protected
    from week2.tests.test_incident_rollback import VALUES
    from week2.abuse import AbuseGate
    from week3.guardrails import LocalRails

    f = ObjectFixture(tmp_path / 'recovery.db')
    stores = f.stores()
    _, keys = protected(identity)
    settings = IAPSettings(AUDIENCE, EMAIL)
    marker = 'private-form-canary'
    values = list(VALUES)
    values[3] = marker
    if stage == 'invalid':
        values[2] = ''
    real = LocalRails.check
    async def decision(self, current, payload):
        if stage == 'missing_input' and current == 'input':
            return True
        if stage == current:
            self.events.append(dict(engine='nemoguardrails', stage=current, executed=True,
                                    code={'input':'protected_action', 'context':'untrusted_context',
                                          'output':'unsupported_output'}[current], outcome='block'))
            return False
        return await real(self, current, payload)
    monkeypatch.setattr(LocalRails, 'check', decision)
    monkeypatch.setattr(AbuseGate, 'admit', lambda *_: {'blocked': stage == 'admission'})
    with TestClient(create_app(settings=settings, verifier=IAPVerifier(settings, keys=keys), stores=stores)) as client:
        response = client.post('/gradio_api/run/recovery',
            headers={'x-goog-iap-jwt-assertion': token(identity)},
            json={'session_hash': 'browser-canary', 'data': [*values, None]})
        assert response.status_code == 200
        html, _, activity = response.json()['data']
    record, = rows(f, STATE, 'telemetry/v1/')
    assert record['request_id'] in activity and record['operation'] == 'recovery'
    stages = record['stages']
    names = ['admission', 'input', 'context', 'output']
    assert [s['stage'] for s in stages] == names
    outcomes = [s['outcome'] for s in stages]
    if stage == 'ok':
        assert outcomes == ['allow'] * 4 and 'Historical incident evidence' in html
    elif stage == 'invalid':
        assert outcomes == ['allow', 'allow', 'not_required', 'allow'] and 'Not required' in activity
    elif stage == 'missing_input':
        assert outcomes == ['allow', 'unavailable', 'not_reached', 'not_reached'] and 'Unavailable' in activity
    else:
        pos = names.index(stage)
        assert outcomes == ['allow'] * pos + ['block'] + ['not_reached'] * (3 - pos)
        assert 'blocked' in html.lower() and 'Blocked' in activity
    assert [s['executed'] for s in stages] == [o in {'allow','block'} for o in outcomes]
    assert not any(v in json.dumps(record) for v in (marker, 'browser-canary', EMAIL, VALUES[2]))
    assert not any(k in record for k in ('question', 'rails', 'history', 'session_id'))


def test_definitive_storage_rejection_records_failed_result(tmp_path, monkeypatch):
    from week2.cloud_storage import WriteRejected
    f = ObjectFixture(tmp_path / 'rejected.db')
    s = f.stores()
    m = s.memory_for(OWNER)
    write = s.client.write
    def reject(bucket, name, row, generation='0'):
        if name == m._name(SERVICE):
            raise WriteRejected('storage_rejected')
        return write(bucket, name, row, generation)
    monkeypatch.setattr(s.client, 'write', reject)
    review = 'a' * 32
    for _ in range(2):
        with pytest.raises(MutationStatus, match='memory_not_saved'):
            m.write(SERVICE, high_risk=True, review_id=review)
    requested, failed = rows(f, AUDIT, 'audit/v1/')
    assert failed['outcome'] == 'failed' and failed['reason'] == 'storage_rejected'
    assert failed['mutation_id'] == requested['mutation_id'] and m.read(SERVICE) is None


def test_signed_browser_redelivery_is_one_preference_mutation(tmp_path, identity):
    from fastapi.testclient import TestClient
    from week2.cloud_app import create_app
    from week2.iap import IAPVerifier, IAPSettings
    from week2.tests.test_iap import AUDIENCE, OWNER as EMAIL, protected, token
    f = ObjectFixture(tmp_path / 'delivery.db')
    _, keys = protected(identity)
    settings = IAPSettings(AUDIENCE, EMAIL)
    verifier = IAPVerifier(settings, keys=keys)
    assertion = token(identity)
    m = f.stores().memory_for(verifier.verify(assertion).key)
    body = dict(session_hash='synthetic-session', data=[
        'Remember that checkout-service is high-risk.', [], None, None, None, None])
    for delivery in ['b' * 32, 'c' * 32, 'b' * 32]:
        # A new app instance and verified session boundary each time.
        mounted = create_app(settings=settings, verifier=verifier, stores=f.stores())
        with TestClient(mounted) as client:
            response = client.post('/gradio_api/run/ui_response', json=body, headers={
                'x-goog-iap-jwt-assertion': assertion, 'Idempotency-Key': delivery})
            assert response.status_code == 200 and 'Preference saved.' in response.text
    assert f.count(AUDIT, 'audit/v1/') == 4 and f.count(STATE, 'telemetry/v1/') == 2
    assert m.read(SERVICE)['high_risk'] is True
    assert 'synthetic-session' not in json.dumps(rows(f, AUDIT, 'audit/v1/'))


def test_four_lost_generation_races_have_one_failed_result(tmp_path, monkeypatch):
    from week2.cloud_storage import GenerationConflict
    f = ObjectFixture(tmp_path / 'conflicts.db')
    s = f.stores()
    m = s.memory_for(OWNER)
    original = s.client.write
    conflicts = []
    def race(bucket, name, row, generation='0'):
        if name == m._name(SERVICE):
            # A competing, compatible v1 writer wins the exact generation.
            original(bucket, name, m.updated(SERVICE, {}, {'high_risk': False}), generation)
            conflicts.append(generation)
            raise GenerationConflict('generation_conflict')
        return original(bucket, name, row, generation)
    monkeypatch.setattr(s.client, 'write', race)
    review = 'e' * 32
    with pytest.raises(MutationStatus, match='memory_not_saved'):
        m.write(SERVICE, high_risk=True, review_id=review)
    assert len(set(conflicts)) == 4 and m.read(SERVICE)['high_risk'] is False
    requested, result = rows(f, AUDIT, 'audit/v1/')
    assert requested['mutation_id'] == result['mutation_id']
    assert result['reason'] == 'generation_conflicts'


def test_repair_windows_do_not_resurrect_expired_records(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from week2 import preference_journal
    from week2.reconcile_review import reconcile
    f = ObjectFixture(tmp_path / 'expiry.db')
    s = f.stores()
    m = s.memory_for(OWNER)
    review = 'f' * 32
    m.write_review(review, SERVICE, high_risk=True)
    created = datetime.fromisoformat(m.journal.load(review)[0]['created'])
    class Clock(datetime):
        days = 7
        @classmethod
        def now(cls, tz=None):
            return created.astimezone(tz or timezone.utc) + timedelta(days=cls.days)
    monkeypatch.setattr(preference_journal, 'datetime', Clock)
    assert reconcile(s.settings, s.client, review) == 'telemetry_expired'
    assert f.count(STATE, 'telemetry/v1/') == 0
    Clock.days = 30
    f.cleanup(30 * DAY)
    assert reconcile(s.settings, s.client, review) == 'expired'
    with pytest.raises(MutationStatus, match='memory_unconfirmed'):
        m.write(SERVICE, high_risk=True, review_id=review)
    assert f.count(AUDIT, 'audit/v1/') == 0


def test_runtime_uses_only_create_for_audit_and_telemetry(tmp_path, monkeypatch):
    f = ObjectFixture(tmp_path / 'restricted.db')
    s = f.stores()
    original = s.client._request
    writes = []
    def restricted(method, url, **kwargs):
        query = kwargs.get('params') or {}
        if '/o/' in url and ('audit-synthetic' in url or 'telemetry%2Fv1' in url):
            pytest.fail('runtime attempted a private receipt read')
        if query.get('name', '').startswith(('audit/v1/', 'telemetry/v1/')):
            assert method == 'POST' and query['ifGenerationMatch'] == '0'
            writes.append(query['name'])
        return original(method, url, **kwargs)
    monkeypatch.setattr(s.client, '_request', restricted)
    m = s.memory_for(OWNER)
    review = '0' * 32
    m.write_review(review, SERVICE, high_risk=True)
    m.confirm_telemetry({'request_id': review, 'status': 'memory_saved', 'transport': 'browser',
                         'duration_ms': 2}, s.telemetry)
    assert len(set(writes)) == len(writes) == 3


def test_locked_audit_result_rejects_early_overwrite_and_delete(tmp_path):
    import httpx
    from week2.cloud_storage import WriteRejected
    fixture = ObjectFixture(tmp_path / 'locked.db')
    s = fixture.stores()
    m = s.memory_for(OWNER)
    m.write(SERVICE, high_risk=True)
    _, result = rows(fixture, AUDIT, 'audit/v1/')
    name = 'audit/v1/' + result['event_key'] + '.json'
    old, generation = s.client.read(AUDIT, name)
    fixture.now = 30 * DAY - 1
    with pytest.raises(WriteRejected):
        s.client.write(AUDIT, name, dict(old, outcome='failed'), generation)
    response = fixture.handle(httpx.Request('DELETE', 'https://storage.googleapis.com/storage/v1/b/'
        + AUDIT + '/o/' + name, headers=s.client._headers()))
    assert response.status_code == 403 and response.json()['error'] == 'retentionPolicyNotMet'
    assert s.client.read(AUDIT, name) == (old, generation)


def test_unacknowledged_old_submission_cannot_overwrite_a_newer_edit(tmp_path, monkeypatch):
    from week2.reconcile_review import reconcile
    fixture = ObjectFixture(tmp_path / 'late-replay.db')
    stores = fixture.stores()
    m = stores.memory_for(OWNER)
    review = '8' * 32
    original = stores.client.write
    def disconnect(bucket, name, row, generation='0'):
        if name == m._name(SERVICE):
            raise StorageUnavailable('unacknowledged_submission')
        return original(bucket, name, row, generation)
    monkeypatch.setattr(stores.client, 'write', disconnect)
    with pytest.raises(MutationStatus, match='memory_unconfirmed'):
        m.write(SERVICE, freeze_notes='older edit', review_id=review)
    fresh = fixture.stores()
    m = fresh.memory_for(OWNER)
    m.write(SERVICE, freeze_notes='newer edit')
    before = fresh.client.read(STATE, m._name(SERVICE))
    with pytest.raises(MutationStatus):
        m.write(SERVICE, freeze_notes='older edit', review_id=review)
    assert fresh.client.read(STATE, m._name(SERVICE)) == before
    assert reconcile(fresh.settings, fresh.client, review) == 'failed'
    assert fresh.client.read(STATE, m._name(SERVICE)) == before
    terminal = [r for r in rows(fixture, AUDIT, 'audit/v1/') if r['request_id'] == review][-1]
    assert terminal['reason'] == 'superseded_generation'
