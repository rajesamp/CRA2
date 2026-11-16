"""Exercise the real Gradio mount behind the owner-only IAP boundary."""
import json
import time
from types import SimpleNamespace

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from week2 import app, cloud_app
from week2.iap import IAPKeys, IAPSettings, IAPVerifier
from week2.memory import MemoryStore
from week2.abuse import AbuseGate
from week2.owner_audit import OwnerAuditStore


def test_real_gradio_mount_admits_owner_and_blocks_unauthenticated_routes(tmp_path):
    settings = IAPSettings('/projects/123456789/locations/test-region/services/test-service', 'owner@example.test')
    key = ec.generate_private_key(ec.SECP256R1())
    jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid='mount-test', alg='ES256')
    keys = IAPKeys(client=httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'keys':[jwk]}))))
    verifier = IAPVerifier(settings, keys=keys)
    now = int(time.time())
    signed = jwt.encode(dict(iss='https://cloud.google.com/iap',aud=settings.audience,
        sub='synthetic-owner',email=settings.owner_email,iat=now,exp=now+600),key,
        algorithm='ES256',headers={'kid':'mount-test'})
    protected = cloud_app.create_app(settings=settings, verifier=verifier,
        memory_store=MemoryStore(tmp_path/'memory.sqlite3'),
        abuse_gate=AbuseGate(store=OwnerAuditStore(tmp_path/'audit.sqlite3')))
    with TestClient(protected) as client:
        assert client.get('/healthz').status_code == 200
        for path in ('/','/config','/gradio_api/queue/join','/gradio_api/queue/data?session_hash=other'):
            assert client.get(path).status_code == 401
        headers={'x-goog-iap-jwt-assertion':signed}
        config=client.get('/config',headers=headers)
        assert config.status_code==200 and config.json()['components']
        assert config.json()['username']==verifier.verify(signed).key
        assert settings.owner_email not in config.text
        assert client.get('/gradio_api/file=/app/data/team_settings.json',headers=headers).status_code in (403,404)


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
