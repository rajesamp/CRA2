# C4 local verification

On November 23, 2026 the locked Python 3.13.15 environments exercised implementation commit `1e4c1cd84e2baf1759821acf72a1294300fa6132` on `codex/c4-audit-correlation-spec`. The tests used synthetic identities, signed loopback browser sessions and the persistent GCS contract fixture. Cloud Run access and bucket configuration were outside this run.

| Check | Observed result |
|---|---|
| Week 2–4 suite | 540 passed, including 24 C4 cases. All 11 named C2 capacity regressions ran. C1 recorded zero missed blocks in eight cases and zero false blocks in five. |
| Evaluation suites | 56 tests passed. All seven scorer canaries, 18 development and validation cases, four reserved cases, and nine fault cases passed. |
| C3 public controls | All 19 controls passed. Seven guarded callbacks returned their expected dispositions. Independent labeling and adjudication remain on hold. |
| TruLens retrieval | All six frozen cases completed. Mean precision and recall were both 0.833. The collector and scorer recorded zero network attempts. |
| Signed Chrome | All nine C4 scenarios matched the visible message to private storage. On the standard mount, two identical deliberate chat gestures produced separate mutations and a recovery review produced its own telemetry. All three review IDs matched the stored records. |

## Owner-visible outcomes

| Chrome scenario | Observed message or result | Private evidence |
|---|---|---|
| Normal save | Preference saved | Requested and committed events, matching telemetry |
| Required pre-write audit unavailable | Preference was not changed | Original preference absent |
| State storage rejected the write | Preference was not saved | Requested and failed events |
| State storage accepted the write and lost its acknowledgement | Save status unconfirmed | New value present, terminal audit still outstanding |
| Confirmed save with missing terminal audit | Preference saved. Confirmation record incomplete. | New value and request event present |
| Confirmed save with missing telemetry | Preference saved. Confirmation record incomplete. | New value and both audit events present |
| Normal recovery | Historical incident evidence displayed | One recovery telemetry record |
| Successful analysis with unavailable telemetry | Report withheld, confirmation failure displayed | Recovery telemetry absent |
| Admission block during a telemetry outage | Request blocked | Security audit present, recovery telemetry absent |

The storage tests restarted the adapter, raced duplicate and independent edits, and compared exact object generations. Redelivery preserved a newer edit after both an acknowledged commit and an ambiguous submission. In the latter case the operator could close the displaced submission as failed without rewriting the preference. Additional cases exercised each recovery stage, missing receipts, metadata canaries, principal isolation, v1 reads, locked audit protection and seven- and 30-day fixture boundaries.

Repeat the storage and recovery regressions with `week2/.venv/bin/python -m pytest week2/tests/test_audit_correlation.py week2/tests/test_cloud_storage.py -q`. For the Chrome checks run `week2/.venv/bin/python -m evaluation.probe_audit_browser --out /tmp/c4-browser.json` with local Chrome and the repository's Playwright setup. The [operator procedure](../../docs/cloud-durable-storage.md#c4-candidate-and-operator-reconciliation) explains the confirmation windows and the additional journal storage per logical edit.

Hosted CI and deployment are pending. The verification used the local storage fixture for retention and permissions. The owner-only release and invitation hold continue.
