"""Durable owner demo state using the Cloud Storage JSON API and service identity."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import re
from threading import Lock
from time import monotonic
from urllib.parse import quote
from uuid import uuid4

import httpx

from cra2.advisor import CATALOG, TEAM_SETTINGS
from week1.responses import guard
from week2.memory import FIELDS, MemoryUnavailable, _text
from week2.owner_audit import AuditUnavailable
from week2.preference_journal import MutationStatus, PreferenceJournal, fingerprint
from week4.telemetry import TelemetryUnavailable, compact


GOOGLE_STORAGE = 'https://storage.googleapis.com'
METADATA_TOKEN = 'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token'
PREFERENCES = 'preferences/v1/'
AUDIT = 'audit/v1/'
TELEMETRY = 'telemetry/v1/'
AUDIT_DAYS = 30
TELEMETRY_DAYS = 7
MAX_BODY = 16384
HEX64 = re.compile(r'[0-9a-f]{64}\Z')


class StorageUnavailable(ValueError):
    pass


class WriteRejected(StorageUnavailable):
    pass


class GenerationConflict(StorageUnavailable):
    pass


@dataclass(frozen=True)
class StorageSettings:
    state_bucket: str
    audit_bucket: str

    def __post_init__(self):
        if self.state_bucket == self.audit_bucket or any(
            not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,61}[a-z0-9]', name)
            for name in (self.state_bucket, self.audit_bucket)
        ):
            raise ValueError('Separate cloud state and audit buckets are required')


class StorageClient:
    def __init__(self, http=None):
        self.http = http if http is not None else httpx.Client(timeout=3, follow_redirects=False, trust_env=False)
        self._token, self._expires = '', 0.0
        self._lock = Lock()

    def _request(self, method, url, *, headers, params=None, body=None, missing=False):
        try:
            with self.http.stream(method, url, params=params, content=body, headers=headers,
                                  follow_redirects=False) as response:
                if response.status_code == 412:
                    raise GenerationConflict('generation_conflict')
                if method == 'POST' and response.status_code in {400, 401, 403, 404}:
                    raise WriteRejected('storage_rejected')
                if missing and response.status_code == 404:
                    return None
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_bytes(chunk_size=4096):
                    if len(data) + len(chunk) > MAX_BODY:
                        raise StorageUnavailable('storage_response_too_large')
                    data.extend(chunk)
                if url == METADATA_TOKEN and response.headers.get('Metadata-Flavor') != 'Google':
                    raise StorageUnavailable('metadata_identity_unavailable')
                value = json.loads(data)
                if not isinstance(value, dict):
                    raise StorageUnavailable('invalid_storage_response')
                return value
        except (GenerationConflict, WriteRejected):
            raise
        except (httpx.HTTPError, ValueError, UnicodeError, RecursionError):
            raise StorageUnavailable('storage_unavailable') from None

    def _headers(self):
        with self._lock:
            if monotonic() >= self._expires:
                row = self._request('GET', METADATA_TOKEN, headers={'Metadata-Flavor': 'Google'})
                token, ttl = row.get('access_token'), row.get('expires_in')
                if (not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9._~+/=-]{1,4096}', token)
                        or type(ttl) is not int or not 5 < ttl <= 3600):
                    raise StorageUnavailable('metadata_identity_unavailable')
                self._token, self._expires = token, monotonic() + max(1, ttl - 60)
            return {'Authorization': 'Bearer ' + self._token}

    def bucket(self, bucket):
        return self._request('GET', f'{GOOGLE_STORAGE}/storage/v1/b/{bucket}', headers=self._headers(),
            params={'fields': 'iamConfiguration,retentionPolicy,lifecycle,softDeletePolicy,versioning'})

    def read(self, bucket, name):
        for _ in range(4):
            try:
                return self._read_generation(bucket, name)
            except GenerationConflict:
                continue
        raise GenerationConflict('object_changed')

    def _read_generation(self, bucket, name):
        url = f'{GOOGLE_STORAGE}/storage/v1/b/{bucket}/o/{quote(name, safe="")}'
        metadata = self._request('GET', url, params={'fields': 'generation'},
                                 headers=self._headers(), missing=True)
        if metadata is None:
            return None, '0'
        generation = metadata.get('generation')
        if not isinstance(generation, str) or not re.fullmatch(r'[1-9][0-9]{0,19}', generation):
            raise StorageUnavailable('invalid_object_generation')
        # The bytes must belong to the same generation as the metadata. A
        # concurrent change between requests is a conflict, never an empty read.
        data = self._request('GET', url, params={'alt': 'media', 'ifGenerationMatch': generation},
                             headers=self._headers(), missing=True)
        if data is None:
            raise GenerationConflict('object_changed')
        return data, generation

    def write(self, bucket, name, row, generation='0'):
        guard(row)
        body = json.dumps(row, allow_nan=False, sort_keys=True, separators=(',', ':')).encode()
        if len(body) > MAX_BODY:
            raise StorageUnavailable('object_too_large')
        self._request('POST', f'{GOOGLE_STORAGE}/upload/storage/v1/b/{bucket}/o',
                      params={'uploadType': 'media', 'name': name, 'ifGenerationMatch': generation,
                              'fields': 'name'},
                      headers={**self._headers(), 'Content-Type': 'application/json'}, body=body)


def _check_policy(meta, prefix, days, *, locked=False):
    iam = meta.get('iamConfiguration', {})
    if (iam.get('uniformBucketLevelAccess', {}).get('enabled') is not True
            or iam.get('publicAccessPrevention') != 'enforced'
            or meta.get('versioning', {}).get('enabled', False) is not False
            or str(meta.get('softDeletePolicy', {}).get('retentionDurationSeconds', '0')) != '0'):
        raise StorageUnavailable('unexpected_bucket_access_or_version_policy')
    rule = {'action': {'type': 'Delete'}, 'condition': {'age': days, 'matchesPrefix': [prefix]}}
    if meta.get('lifecycle', {}).get('rule') != [rule]:
        raise StorageUnavailable('unexpected_lifecycle_policy')
    retention = meta.get('retentionPolicy', {})
    if locked:
        if retention.get('isLocked') is not True or str(retention.get('retentionPeriod')) != str(days * 86400):
            raise StorageUnavailable('unexpected_audit_retention_policy')
    elif retention:
        raise StorageUnavailable('unexpected_state_retention_policy')


class CloudAudit:
    def __init__(self, settings, client):
        self.settings, self.client = settings, client
        self._lock = Lock()
        self._verified_until = 0.0

    def ensure(self):
        try:
            with self._lock:
                if monotonic() < self._verified_until:
                    return
                _check_policy(self.client.bucket(self.settings.state_bucket), TELEMETRY, TELEMETRY_DAYS)
                _check_policy(self.client.bucket(self.settings.audit_bucket), AUDIT, AUDIT_DAYS, locked=True)
                self._verified_until = monotonic() + 60
        except (ValueError, TypeError, AttributeError):
            raise AuditUnavailable('audit_unavailable') from None

    def append(self, _question, client_hash, kind, verdict):
        try:
            if (not isinstance(client_hash, str) or not HEX64.fullmatch(client_hash)
                    or kind not in {'out_of_scope', 'suspected_adversarial', 'security_unavailable',
                                    'sensitive_input', 'memory_write_requested'} or not isinstance(verdict, dict)):
                raise ValueError
            self.ensure()
            # Only known verdict fields cross the durable audit boundary.
            details = {k: verdict[k] for k in ('classification', 'severity', 'action', 'service', 'outcome')
                       if k in verdict}
            row = {'kind': kind, 'client_hash': client_hash, 'verdict': details,
                   'created_at': datetime.now(timezone.utc).isoformat()}
            self.client.write(self.settings.audit_bucket, AUDIT + uuid4().hex + '.json', row)
        except (ValueError, TypeError):
            raise AuditUnavailable('audit_unavailable') from None


class CloudPreferences:
    def __init__(self, bucket, client, audit, scope):
        if not isinstance(scope, str) or not HEX64.fullmatch(scope):
            raise ValueError('invalid_private_scope')
        self.team, self.scope = TEAM_SETTINGS['team'], scope
        self.bucket, self.client, self.audit = bucket, client, audit
        self.journal = PreferenceJournal(self)

    def _name(self, service):
        if service not in CATALOG:
            raise ValueError('Invalid preference service')
        return f'{PREFERENCES}{self.scope}/{service}.json'

    def _read(self, service, name):
        record, generation = self.client.read(self.bucket, name)
        if record is None:
            # A missing bucket can also return 404. Never turn a storage
            # outage into a successful read with no risk preference.
            _check_policy(self.client.bucket(self.bucket), TELEMETRY, TELEMETRY_DAYS)
        else:
            guard(record)
            receipt = record.get('_receipt')
            if '_receipt' in record and (not isinstance(receipt, dict)
                    or set(receipt) != {'request_id', 'mutation_id', 'service'} or receipt['service'] != service
                    or any(not re.fullmatch(r'[0-9a-f]{32}', receipt[k]) for k in ('request_id', 'mutation_id'))):
                raise ValueError('Invalid preference receipt')
            if (set(record) - {'_receipt'} != set(FIELDS) or record['team'] != self.team or record['service'] != service
                    or record['source'] != 'explicit_team_preference'
                    or (record['high_risk'] is not None and type(record['high_risk']) is not bool)
                    or (record['freeze_notes'] is not None and not _text(record['freeze_notes'], 500))
                    or not _text(record['updated_at'], 50)
                    or datetime.fromisoformat(record['updated_at']).utcoffset() is None):
                raise ValueError('Invalid preference record')
        return record, generation

    def read(self, service):
        try:
            name = self._name(service)
            for _ in range(4):
                try:
                    row, _ = self._read(service, name)
                    return {k: row[k] for k in FIELDS} if row else None
                except GenerationConflict:
                    continue
        except (ValueError, TypeError):
            pass
        raise MemoryUnavailable('memory_unavailable')

    def updated(self, service, previous, updates):
        return dict(team=self.team, service=service, source='explicit_team_preference',
                    updated_at=datetime.now(timezone.utc).isoformat(),
                    high_risk=updates.get('high_risk', previous.get('high_risk')),
                    freeze_notes=updates.get('freeze_notes', previous.get('freeze_notes')))

    def _write(self, review_id, service, high_risk, freeze_notes, telemetry_required):
        try:
            self._name(service)
            guard([high_risk, freeze_notes])
            if ((high_risk is None and freeze_notes is None)
                    or (high_risk is not None and type(high_risk) is not bool)
                    or (freeze_notes is not None and not _text(freeze_notes, 500))):
                raise MutationStatus('memory_not_changed')
            updates = {k: v for k, v in (('high_risk', high_risk), ('freeze_notes', freeze_notes)) if v is not None}
            return self.journal.apply(review_id, service, updates, telemetry_required=telemetry_required)
        except MutationStatus:
            raise
        except AuditUnavailable:
            raise MutationStatus('memory_not_changed') from None
        except (TypeError, ValueError):
            raise MutationStatus('memory_unconfirmed') from None

    def write(self, service, *, high_risk=None, freeze_notes=None, review_id=None):
        return self._write(review_id or uuid4().hex, service, high_risk, freeze_notes, False)

    def write_review(self, review, service, *, high_risk=None, freeze_notes=None):
        return self._write(review, service, high_risk, freeze_notes, True)

    def confirm_telemetry(self, trace, telemetry):
        review = trace['request_id']
        digest = fingerprint(compact(trace))
        try:
            for _ in range(6):
                op, version = self.journal.load(review)
                if not op or op['scope'] != self.scope or op['phase'] != 'committed':
                    raise TelemetryUnavailable('missing_write_proof')
                if op.get('telemetry_confirmed'):
                    return
                if datetime.now(timezone.utc) - datetime.fromisoformat(op['created']) >= timedelta(days=TELEMETRY_DAYS):
                    raise TelemetryUnavailable('telemetry_expired')
                try:
                    if not op.get('telemetry_expected'):
                        self.journal.update(op, version, telemetry_expected=digest)
                        continue
                    if op['telemetry_expected'] != digest:
                        raise TelemetryUnavailable('telemetry_reconciliation_required')
                    telemetry.write(trace)
                    self.journal.update(op, version, telemetry_confirmed=True)
                    return
                except GenerationConflict:
                    continue
        except (ValueError, KeyError):
            pass
        raise TelemetryUnavailable('telemetry_unavailable')


class CloudTelemetry:
    def __init__(self, bucket, client):
        self.bucket, self.client = bucket, client

    def write(self, trace):
        try:
            record = compact(trace)
            if not re.fullmatch(r'[0-9a-f]{32}', record['request_id']):
                raise ValueError
            self.client.write(self.bucket, TELEMETRY + record['request_id'] + '.json', record)
        except (ValueError, TypeError, KeyError):
            raise TelemetryUnavailable('telemetry_unavailable') from None


class CloudStores:
    def __init__(self, settings, *, client=None):
        self.settings = settings
        self.client = client if client is not None else StorageClient()
        self.audit = CloudAudit(settings, self.client)
        self.telemetry = CloudTelemetry(settings.state_bucket, self.client)

    @classmethod
    def from_env(cls):
        return cls(StorageSettings(os.environ.get('CRA2_STATE_BUCKET', ''), os.environ.get('CRA2_AUDIT_BUCKET', '')))

    def memory_for(self, principal):
        if (not isinstance(principal, str) or not principal.startswith('iap:')
                or not HEX64.fullmatch(principal[4:])):
            raise MemoryUnavailable('memory_unavailable')
        scope = hashlib.sha256((principal + '\0' + TEAM_SETTINGS['team']).encode()).hexdigest()
        return CloudPreferences(self.settings.state_bucket, self.client, self.audit, scope)
