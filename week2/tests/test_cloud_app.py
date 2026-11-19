"""Exercise the real Gradio mount behind the owner-only IAP boundary."""
import json
import time
from inspect import unwrap
from types import SimpleNamespace

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from week2 import app, cloud_app
from week2.iap import IAPKeys, IAPSettings, IAPVerifier
from week2.tests.test_cloud_storage import ObjectFixture, STATE, AUDIT, SERVICE


def test_real_gradio_mount_admits_owner_and_blocks_unauthenticated_routes(tmp_path, monkeypatch):
    settings = IAPSettings('/projects/123456789/locations/test-region/services/test-service', 'owner@example.test')
    key = ec.generate_private_key(ec.SECP256R1())
    jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid='mount-test', alg='ES256')
    keys = IAPKeys(client=httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'keys':[jwk]}))))
    verifier = IAPVerifier(settings, keys=keys)
    now = int(time.time())
    def sign(email):
        return jwt.encode(dict(iss='https://cloud.google.com/iap', aud=settings.audience,
            sub='synthetic-owner', email=email, iat=now, exp=now+600), key,
            algorithm='ES256', headers={'kid':'mount-test'})

    signed = sign(settings.owner_email)
    fixture = ObjectFixture(tmp_path/'objects.sqlite3')
    stores = fixture.stores()
    built = []
    def capture(**kwargs):
        built.append(app.build_app(**kwargs))
        return built[-1]
    monkeypatch.setattr(cloud_app, 'build_app', capture)
    monkeypatch.setattr(app, 'TelemetryStore', lambda *_a, **_k: pytest.fail('cloud fell back to local telemetry'))
    protected = cloud_app.create_app(settings=settings, verifier=verifier, stores=stores)
    with TestClient(protected) as client:
        assert client.get('/healthz').status_code == 200
        for path in ('/','/config','/gradio_api/queue/join','/gradio_api/queue/data?session_hash=other'):
            assert client.get(path).status_code == 401
        assert client.get('/config', headers={'x-goog-iap-jwt-assertion': sign('other@example.test')}).status_code == 403
        headers={'x-goog-iap-jwt-assertion':signed}
        config=client.get('/config',headers=headers)
        assert config.status_code==200 and config.json()['components']
        assert config.json()['username']==verifier.verify(signed).key
        assert settings.owner_email not in config.text
        assert client.get('/gradio_api/file=/app/data/team_settings.json',headers=headers).status_code in (403,404)
        identity = config.json()['username']
        reply = next(unwrap(fn.fn) for fn in built[0].fns.values() if fn.fn and fn.fn.__name__ == 'reply')
        result = reply('Remember that checkout-service is always high-risk for our team.', [],
                       'Local evidence only', 'synthetic-session', [], SimpleNamespace(username=identity))
        assert result[2][-1]['status'] == 'memory_saved'
        assert fixture.stores().memory_for(identity).read(SERVICE)['high_risk'] is True
        assert fixture.count(AUDIT, 'audit/v1/') == fixture.count(STATE, 'telemetry/v1/') == 1


def test_cloud_abuse_identity_cannot_fall_back_to_proxy_or_browser_headers():
    identity='iap:'+'a'*64
    request=SimpleNamespace(username=identity,client=SimpleNamespace(host='proxy'))
    assert cloud_app.request_identity(request)==identity
    for invalid in (None, '', 'proxy', 'iap:spoofed'):
        request.username=invalid
        with pytest.raises(ValueError):cloud_app.request_identity(request)


def test_local_entrypoint_refuses_cloud_run(monkeypatch):
    monkeypatch.setenv('K_SERVICE','synthetic-service')
    monkeypatch.setattr(app,'build_app',lambda **kwargs:SimpleNamespace(launch=lambda **kw:None))
    with pytest.raises(RuntimeError,match='Cloud Run'):app.main([])


def test_cloud_configuration_fails_before_app_build(monkeypatch):
    monkeypatch.delenv('CRA2_IAP_AUDIENCE',raising=False)
    monkeypatch.delenv('CRA2_OWNER_EMAIL',raising=False)
    monkeypatch.setattr(cloud_app,'build_app',lambda **kw:pytest.fail('unconfigured app was built'))
    with pytest.raises(ValueError):cloud_app.create_app()


def test_valid_iap_configuration_requires_both_cloud_buckets(monkeypatch):
    settings = IAPSettings('/projects/123456789/locations/test-region/services/test-service', 'owner@example.test')
    monkeypatch.setenv('CRA2_STATE_BUCKET', STATE)
    monkeypatch.delenv('CRA2_AUDIT_BUCKET', raising=False)
    monkeypatch.setattr(cloud_app, 'build_app', lambda **kw: pytest.fail('cloud used a fallback store'))
    with pytest.raises(ValueError, match='Separate cloud state and audit buckets'):
        cloud_app.create_app(settings=settings)
