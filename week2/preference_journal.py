"""Generation-fenced preference mutations. Audit reads require a separate operator."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from uuid import uuid4

from week2.memory import MemoryUnavailable


class MutationStatus(MemoryUnavailable):
    def __init__(self, status):
        self.status = status
        super().__init__(status)


MESSAGES = {
    'memory_not_changed': 'Preference was not changed.',
    'memory_replay_rejected': 'This submission could not be matched. Preference was not changed.',
    'memory_not_saved': 'Preference was not saved.',
    'memory_unconfirmed': 'Save status unconfirmed.',
    'memory_confirmation_incomplete': 'Preference saved. Confirmation record incomplete.',
}


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def fingerprint(value):
    data = json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':'))
    return hashlib.sha256(data.encode()).hexdigest()


def journal_name(review):
    if not isinstance(review, str) or not re.fullmatch(r'[a-f0-9]{32}', review):
        raise ValueError('invalid_review_id')
    return 'preferences/v1/operations/' + review + '.json'


def audit_event(op, terminal):
    outcome = op['phase'] if terminal else 'requested'
    key = op['mutation_id'] + ('-result' if terminal else '-request')
    row = dict(schema_version=2, event_key=key, kind='memory_write_' + outcome,
               request_id=op['request_id'], mutation_id=op['mutation_id'], scope=op['scope'],
               service=op['service'], outcome=outcome, created_at=op['ended'] if terminal else op['created'])
    if outcome == 'committed':
        row['generation'] = op['generation']
    if outcome == 'failed':
        row['reason'] = op['failure']
    return 'audit/v1/' + key + '.json', row


class PreferenceJournal:
    def __init__(self, memory):
        self.memory = memory
        self.client, self.bucket = memory.client, memory.bucket

    def load(self, review):
        return self.client.read(self.bucket, journal_name(review))

    def update(self, op, journal_generation, **changes):
        self.client.write(self.bucket, journal_name(op['request_id']), dict(op, **changes), journal_generation)

    def checkpoint(self, receipt, generation):
        """A newer edit must preserve the displaced write's proof before its CAS."""
        from week2.cloud_storage import GenerationConflict
        for _ in range(8):
            op, version = self.load(receipt['request_id'])
            if (not op or receipt['mutation_id'] != op['mutation_id'] or op['scope'] != self.memory.scope
                    or op['service'] != receipt['service']):
                raise ValueError('unverified_receipt')
            if op['phase'] == 'committed' and op['generation'] == generation:
                return
            if op['phase'] != 'submitting':
                raise ValueError('invalid_mutation_phase')
            try:
                self.update(op, version, phase='committed', generation=generation, ended=utcnow())
                return
            except GenerationConflict:
                continue
        raise MemoryUnavailable('checkpoint_unavailable')

    def append(self, op, terminal, operator=None):
        """A 412 alone never acknowledges a supposedly immutable record."""
        from week2.cloud_storage import GenerationConflict
        name, event = audit_event(op, terminal)
        bucket = self.memory.audit.settings.audit_bucket
        self.memory.audit.ensure()
        try:
            self.client.write(bucket, name, event)
        except GenerationConflict:
            if operator is None or operator.read(bucket, name)[0] != event:
                raise

    def finish(self, op, version, *, need_value):
        committed = op['phase'] == 'committed'
        if not op.get('audit_confirmed'):
            try:
                self.append(op, True)
                self.update(op, version, audit_confirmed=True)
            except ValueError:
                try:
                    latest, _ = self.load(op['request_id'])
                except ValueError:
                    latest = {}
                if not latest.get('audit_confirmed'):
                    raise MutationStatus('memory_confirmation_incomplete' if committed else 'memory_not_saved') from None
        if not committed:
            raise MutationStatus('memory_not_saved')
        if need_value:
            return self.memory.read(op['service'])
        return None

    def apply(self, review, service, updates, *, telemetry_required=False):
        from week2.cloud_storage import GenerationConflict, StorageUnavailable, WriteRejected
        binding = fingerprint([self.memory.scope, service, updates])
        name = self.memory._name(service)
        # CAS failures on the journal are coordination, not rejected state writes.
        for _ in range(24):
            op, version = self.load(review)
            if op is None:
                self.memory.audit.ensure()
                op = dict(request_id=review, mutation_id=uuid4().hex, scope=self.memory.scope,
                          service=service, binding=binding, created=utcnow(), phase='new', attempts=0,
                          telemetry_required=telemetry_required)
                try:
                    self.update(op, version)
                except GenerationConflict:
                    pass
                continue
            if (op['scope'], op['service'], op['binding']) != (self.memory.scope, service, binding):
                raise MutationStatus('memory_replay_rejected')
            if datetime.now(timezone.utc) - datetime.fromisoformat(op['created']) >= timedelta(days=30):
                raise MutationStatus('memory_unconfirmed')
            phase = op['phase']
            if phase in {'failed', 'committed'}:
                return self.finish(op, version, need_value=not telemetry_required)
            if phase == 'new':
                try:
                    self.append(op, False)
                    self.update(op, version, phase='requested')
                except ValueError as error:
                    latest, _ = self.load(review)
                    if latest['phase'] == 'new':
                        raise MutationStatus('memory_unconfirmed' if isinstance(error, GenerationConflict)
                                             else 'memory_not_changed') from None
                continue
            previous, generation = self.memory._read(service, name)
            receipt = previous.get('_receipt') if previous else None
            if receipt:
                self.checkpoint(receipt, generation)
                if receipt['request_id'] == review:
                    continue
            # Re-read after the value. If a different writer displaced our
            # receipt, its checkpoint is now visible; a stale value CAS loses.
            _, current_version = self.load(review)
            if current_version != version:
                continue
            if phase == 'submitting' and op['expected'] == generation:
                # Another delivery owns this conditional write. Its acknowledgement
                # may have been lost. No second caller may declare failure or submit it.
                raise MutationStatus('memory_unconfirmed')
            try:
                if op['attempts'] >= 4:
                    self.update(op, version, phase='failed', failure='generation_conflicts', ended=utcnow())
                    continue
                self.memory.audit.ensure()
                self.update(op, version, phase='submitting', expected=generation, attempts=op['attempts'] + 1)
            except GenerationConflict:
                continue
            record = self.memory.updated(service, previous or {}, updates)
            proof = dict(request_id=review, mutation_id=op['mutation_id'], service=service)
            try:
                self.client.write(self.bucket, name, dict(record, _receipt=proof), generation)
            except GenerationConflict:
                continue
            except WriteRejected:
                current, version = self.load(review)
                if current['phase'] == 'submitting' and current['expected'] == generation:
                    try:
                        self.update(current, version, phase='failed', failure='storage_rejected', ended=utcnow())
                    except GenerationConflict:
                        continue
                continue
            except StorageUnavailable:
                raise MutationStatus('memory_unconfirmed') from None
            try:
                # A later writer can advance this object only after checkpointing us.
                current, committed_generation = self.memory._read(service, name)
                if current and current.get('_receipt') == proof:
                    self.checkpoint(proof, committed_generation)
                latest, version = self.load(review)
                if latest['phase'] != 'committed':
                    raise MemoryUnavailable('checkpoint_unavailable')
                self.finish(latest, version, need_value=False)
                return record
            except ValueError:
                raise MutationStatus('memory_confirmation_incomplete') from None
        raise MutationStatus('memory_unconfirmed')

    def reconcile(self, review, operator):
        """Repair receipts only. Never submit a preference value during reconciliation."""
        from week2.cloud_storage import GenerationConflict
        for _ in range(12):
            op, version = self.load(review)
            if op is None or op['scope'] != self.memory.scope:
                raise ValueError('unknown_review')
            age = datetime.now(timezone.utc) - datetime.fromisoformat(op['created'])
            if age >= timedelta(days=30):
                return 'expired'
            phase = op['phase']
            try:
                if phase == 'new':
                    self.append(op, False, operator)
                    self.update(op, version, phase='requested')
                    continue
                if phase in {'requested', 'submitting'}:
                    current, generation = self.memory._read(op['service'], self.memory._name(op['service']))
                    receipt = (current or {}).get('_receipt', {})
                    if receipt.get('mutation_id') != op['mutation_id']:
                        return 'unconfirmed'
                    self.checkpoint(receipt, generation)
                    continue
                if not op.get('audit_confirmed'):
                    self.append(op, True, operator)
                    self.update(op, version, audit_confirmed=True)
                    continue
                if phase == 'committed' and op.get('telemetry_required') and not op.get('telemetry_confirmed'):
                    if age >= timedelta(days=7):
                        return 'telemetry_expired'
                    name = 'telemetry/v1/' + review + '.json'
                    actual, _ = operator.read(self.bucket, name)
                    # A repaired record identifies lost measurements explicitly.
                    repair = dict(schema_version=2, operation='preference', request_id=review,
                                  status=phase, recorded_at=op['ended'], measurements='unavailable')
                    if actual is None:
                        self.client.write(self.bucket, name, repair)
                    elif actual != repair and fingerprint(actual) != op.get('telemetry_expected'):
                        return 'telemetry_mismatch'
                    self.update(op, version, telemetry_confirmed=True)
                    continue
                return phase
            except GenerationConflict:
                continue
        return 'unconfirmed'
