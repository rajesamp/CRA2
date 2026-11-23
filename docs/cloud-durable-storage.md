# Owner-only cloud storage

Live verification on 2026-11-17 confirmed the owner-approved permanent 30-day
audit lock. A new audit record rejected early overwrite and deletion with
`retentionPolicyNotMet` and remained readable by the operator. The runtime keeps
create-only audit access. Two fresh Cloud Run executions using the signed
release and dedicated runtime identity wrote and recalled a synthetic preference
through the actual application adapter. They also verified both bucket policies
and allowed/denied HTTPS egress. See the
[bounded evidence](../intent/cloud-durable-storage/live-owner-rollout.json).
Owner Google login, a tool-backed local review and the memory-policy read now
succeed through the live browser. A deployment-approval request was blocked at
admission; its metadata-only audit was read back with 30-day retention. See the
[browser evidence](../intent/cloud-durable-storage/live-owner-browser.json).
Age-based lifecycle deletion has not yet been observed. Owner product acceptance
remains pending; invitations stay on hold.

The Cloud Run entrypoint requires `CRA2_STATE_BUCKET` and `CRA2_AUDIT_BUCKET`,
alongside the existing owner and IAP audience configuration. The runtime uses
its attached service identity. It checks bucket policy when the owner first
submits a chat request and refreshes the check within 60 seconds. Missing or
incompatible policy blocks the request. `/healthz` reports process liveness.

| Bucket | Objects | Policy |
|---|---|---|
| State | `preferences/v1/<scope>/<service>.json` | Keep the current value. Generation preconditions prevent lost updates. Scope derives from the verified IAP subject and configured team. |
| State | `telemetry/v1/<request-id>.json` | Delete after seven days of object age. Contains the compact request metrics already used locally. |
| Audit | `audit/v1/<event-id>.json` | Lock retention for 30 days and set lifecycle deletion at 30 days. Each event is create-only and omits question text, notes, tokens and raw outputs. |

The seven- and 30-day periods are configured; the owner approved and applied the
irreversible 30-day audit retention lock. Both
buckets require uniform access, enforced public access prevention, disabled
object versioning, and disabled soft delete. Review the loss of recovery for
accidentally deleted state before adopting these settings in the demo project.
Lifecycle deletion is asynchronous. The age rules define eligibility for
deletion. [Object Lifecycle Management](https://docs.cloud.google.com/storage/docs/lifecycle)
and [soft delete](https://docs.cloud.google.com/storage/docs/soft-delete).

Set the state lifecycle policy to the first document below and the audit
lifecycle to the second. Keep those as the only lifecycle rules on each dedicated
bucket. The application verifies the exact policies.

```json
{"rule":[{"action":{"type":"Delete"},"condition":{"age":7,"matchesPrefix":["telemetry/v1/"]}}]}
```

```json
{"rule":[{"action":{"type":"Delete"},"condition":{"age":30,"matchesPrefix":["audit/v1/"]}}]}
```

## IAM and live verification

- Grant the runtime `storage.buckets.get` on the two bucket resources. Keep
  bucket configuration changes with the operator.
- On the state bucket restrict `storage.objects.get`, `storage.objects.create`,
  and `storage.objects.delete` to the preference prefix. Cloud Storage requires
  delete permission to replace an existing live object. Grant create only for
  the telemetry prefix. Use a custom role and prefix IAM conditions using
  `resource.name.startsWith('projects/_/buckets/<bucket>/objects/<prefix>')`.
- On the audit bucket grant runtime create only, scoped to `audit/v1/`. Audit
  reads use a separate, authorized operator identity. Check effective inherited
  permissions before using the runtime identity. [Cloud Storage IAM roles](https://docs.cloud.google.com/storage/docs/access-control/iam-roles).
- Allow runtime egress to the service metadata endpoint, Google Storage API, and
  IAP public keys through the approved egress path. Confirm API reads and writes
  succeed, and unrelated destinations remain denied.
- An operator verifies audit retention first on a dedicated test bucket. Check
  that premature replacement and deletion are denied, that a create-only caller
  cannot read or delete audit objects, and that aged synthetic objects become
  eligible for lifecycle cleanup. Review an exact bucket configuration before
  applying the irreversible production lock. [Bucket Lock](https://docs.cloud.google.com/storage/docs/bucket-lock).
- Verify the deployed owner's preference and audit attempt survive an instance
  restart and are readable from a second instance by the appropriate identity.
  Compare billed API requests and latency with the $10/month demo target.

### C4 candidate and operator reconciliation

The C4 candidate writes a requested audit event before submitting a preference update and a committed or failed event once the outcome is known. Both include the review ID shown in Guardrail activity, a mutation ID and a stable event key. The committed event identifies the exact object generation. Older request-only events have unknown completion. The owner-only route verifies identity before resolving preferences.

Each private journal at `preferences/v1/operations/<review-id>.json` binds the authenticated scope, service and fingerprint of the intended change. It contains bounded metadata. The service record holds one write receipt. A later edit checkpoints its predecessor before replacing that receipt. Journals share preference storage permissions and persistence. Their storage grows by one small object per logical edit. Their presence prevents reuse of an expired review ID. Keep them out of user-facing exports.

For a missing receipt, an authorized operator can run `python -m week2.reconcile_review REVIEW_ID` with the existing bucket environment and a selected gcloud account that has state access and audit read/create access. This command checks retention and repairs only confirmation records. It verifies an existing immutable object against the expected record. A missing measurement is explicitly marked unavailable. An unresolved state write stays unconfirmed until its exact receipt can be established. Investigate a persistent mismatch using the private journal and both generations. Avoid replaying the change as a fresh edit while its status is unknown.

The operator can repair telemetry during the first seven days and audit receipts during the first 30 days after submission. At most four distinct state generations are attempted. The bucket lifecycle remains authoritative for actual deletion. Recovery records live only under the seven-day telemetry prefix and contain four bounded stage decisions. A telemetry outage withholds a successful report. A security block remains visible.

The C4 reader accepts v1 preferences. The earlier binary rejects C4 values containing a receipt. Rolling back to that binary after a C4 write needs a compatible reader or a separately tested migration. Keep the owner-only deployment on the approved revision until release verification.

The cloud prefix starts empty. The local demo retains its SQLite behavior and
files. For cloud rollback preserve the buckets and `v1` object format, and use a
previous verified revision that supports that format. For the first revision,
stop owner access and keep the state and audit evidence. Invitations remain on
hold until owner testing and explicit approval.
