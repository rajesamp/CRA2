# Show which rollout and rollback details are missing

**Draft for owner review · November 23, 2026.** The reviewer should know what would trigger a rollback, what it would restore, and which effects would still need attention. Completing a form supplies a proposed plan. A rehearsal result and an explicit human decision are separate evidence.

## What changes

Guided intake already captures a window, deployment plan, rollback plan and monitoring notes. Its chat handoff deliberately forwards only the service and summary. The recovery prototype already reports compatibility, rehearsal and reconciliation declarations, recorded recovery guidance and blockers. Add an item-by-item checklist to the protected recovery result. Reuse those inputs. If guided intake is integrated, carry its plan fields through a bounded, session-scoped handoff to the checklist after admission. Keep the existing chat handoff intact. The recovery form also works on its own. When it supplies only a summary and a rollback note, use the details they contain and mark the remaining items missing. [Intake schema](https://github.com/rajesamp/CRA2/blob/434f8bc182a9b82a6a0e1bd51420e0bf7c3fdeb4/week2/intake_schema.json) · [Recovery prototype](https://github.com/rajesamp/CRA2/blob/3308ab23e0dac3d23ba7e189b98deaca92bed54b/week2/incident_rollback.py)

| Checklist item | What the reviewer needs |
|---|---|
| Rollout and owner | Target artifact or config, intended first exposure, monitoring window and responsible role. |
| Stop or continue | Signal, threshold and time window that determine when to stop expansion or reverse. |
| Reversal | Previous artifact or value and the intended restoration step. A named strategy alone leaves the target and steps open. |
| Compatibility and persistent effects | How the previous version handles the changed schema or events. Which writes, payments, tokens or other effects need reconciliation, and who checks them. |
| Recovery verification | Post-reversal checks, named signals and an attributable rehearsal outcome for the relevant version. A catalog recovery estimate remains an estimate. |

For example, a synthetic canary plan says “Start with 5% of checkout traffic for 10 minutes. Stop if the error rate exceeds 2% for 5 minutes.” It declares the initial exposure and stop condition. The responsible role, prior artifact and recovery checks are still missing.

Each item shows **Missing**, **Declared**, **Evidence attached**, or **Reported blocker**, plus a specific next check. Use **Evidence attached** only when an admitted local reference resolves to the relevant service, version and check. A typed “Pass” stays a declaration. An explicit failure or conflict stays visible even when a plan field is filled. A “not applicable” declaration needs a rationale and remains attributable to the reviewer. Every state describes evidence completeness. There is no readiness percentage, automated rollback, deployment approval or dataset write. Atomicwork’s rollout examples illustrate plan styles that a reviewer may name. [Vendor description](https://www.atomicwork.com/notes/why-approved-changes-still-cause-outages)

## Acceptance on Python 3.13

- “Roll back if needed” leaves the trigger, restoration target and validation missing. “Not yet defined” stays missing. A canary percentage alone leaves its observation window and stop condition open.
- For a schema change with a known previous image and a reported incompatibility, display the image reference and the compatibility blocker together. Ask how already-written data will be reconciled.
- With a declared passing rehearsal and only an old catalog estimate, show the declaration and the estimate separately. A version-mismatched rehearsal cannot fill the evidence item.
- Exercise canary, blue-green and rolling plan descriptions through the signed fixture. Each can express an exposure step, stop condition and reversal target. Preserve the existing response when admission or required telemetry fails. The other session and public intro receive no plan text.

The reviewer decides what action to take. The access policy, invitations and independent labeling remain under their existing holds.
