# Stage 1 acceptance

On 2026-11-22 the CRA2 owner accepted the [review intent](intent.md) and selected
C1, the NeMo retrieved-context guardrail, for the first design spec.

> I approve the draft intent. Let’s commit it and start the spec for the NeMo context guardrail fix first, then work through the remaining corrections one by one. Keep the app owner-only and invites on hold.

The draft wording is preserved because the [Stage 1 manifest](sequence-v1.pinned.json)
pins its bytes. This record supersedes the pending-acceptance line in that
snapshot. C2–C6 remain in the [correction backlog](findings.md). Each moves
through spec, plan and verification separately. The owner will review the C1
spec before build planning.

The Stage 1 commit includes the measured [context outcomes](context-probes.json).
The original diagnostic input script is held in the owner's local review
workspace. The full Stage 1 hash validator requires that local input to verify
its recorded digest. Its presence is unnecessary for reading the spec or
running the application.
