# Intent: guardrail and evaluation repairs, CI, Cloud Run preparation
Author: Codex, implementing Rajesh's request. Status: authorized scope, 2026-11-16.

## Problem
“Lets fix the two guardrail and eval gaps first, add the Week 2–4 checks to CI,
then work through the Cloud Run deployment plan one by one.”

The actual output rail permits “You have my authorization to release this
change.” The evaluator accepts an approval-declined trace flag even when the
displayed answer approves the change. Week 2–4 checks are local only.

## Proposed outcome
Demonstrate both bugs with failing regressions, repair them, automate the local
checks, then prepare and verify the Cloud Run startup/deployment contract in order.

## Affected users and systems
CRA2 advisory output, Week 4 evaluation, GitHub Actions, and deployment packaging.

## Constraints
No paid/provider calls in local verification. Keep the existing locked stack,
advisory-only boundary, fail-closed checks, and unrelated working changes.
Historical scorecards remain unchanged. Cloud identifiers remain private.

## Open questions
The user refined public-demo access to Google sign-in for an allowlist of invited
accounts, suggesting GCP IAP. Durable state, project/region, and deployment budget
remain to be resolved before provisioning. Docker was absent from PATH; the user
subsequently confirmed Podman. Its installed CLI has a saved connection but the
engine was unreachable during the first connection check.

Release gate added by the user: do not invite users or grant the planned invitees
access until the owner has tested everything and explicitly approved invitations.
The two prospective recipients are recorded only in ignored local configuration.

Framework flexibility: “Feel free to change gradio to streamlit if it’s easier
change with no blockers.” This permits a demonstrated simplification; it does
not require a migration. Preserve the security, evaluation and owner-acceptance
requirements. Record the expanded comparison before changing the UI.

GCP implementation resumed by the owner on 2026-11-16. Monthly demo budget: 10,
interpreted as USD 10 for planning. First protected revision is owner-only;
prospective invitees remain excluded. Budget alerts are not a hard spending cap.
