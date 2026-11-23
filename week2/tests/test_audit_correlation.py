"""C4 uses the same signed endpoints, retention policies and conditional writes as CRA2."""
import json
import sqlite3

import pytest

from week2.tests.test_cloud_storage import AUDIT, STATE, OWNER, SERVICE, ObjectFixture


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
        assert 'confirmation incomplete' in activity.lower()
        assert fixture.count(STATE, 'telemetry/v1/') == 0


from week2.tests.test_iap import identity  # registered signed-owner fixture
