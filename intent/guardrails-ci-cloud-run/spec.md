# Spec: guardrails, evaluation, CI and startup contract
Author: Codex. Input: intent.md, authorized by the user's 2026-11-16 instruction.

## Requirements
1. The actual NeMo output rail blocks the demonstrated authorization wording and
   explicit approval/clearance variants, even with the advisory suffix present.
   Ordinary refusal, requests for human authorization and incident history work.
2. Evaluation requires an explicit visible refusal for refusal cases, and rejects
   contradictory authorization despite a true trace flag. Scoring has independent
   text checks and negative canaries; old scorecards are not relabeled.
3. CI installs the Week 2 lock, provisions the checksum-verified local encoder,
   then runs Week 2–4 tests, development/validation, corrected reserved cases,
   scorer canaries and nine injected faults without provider credentials.
4. Cloud Run preparation starts with an explicit bind/PORT contract and readiness
   checks. Deployment advances only after its storage, identity and security
   requirements have concrete evidence.

## Design
Keep runtime output matching in week3/guardrails.py. Add independently maintained
visible-answer checks to week4/evaluate.py. Keep core contract and memory-session
answers in the evaluation boundary. Add a dedicated Week 2–4 workflow.
Extend week2/app.py startup without changing the local loopback default.

## Policy conformance
Follow the parent AGENTS.md security and secrecy requirements and the active
SDLC/surgical-patch skills. Preserve the previously accepted exact tool-descriptor
gate. Local models remain checksum pinned; no model-dependent safety calls added.

## Flagged concerns
Deterministic language checks have bounded coverage, not a semantic-safety proof.
Local test passes do not prove GitHub's Linux runner or deployed Cloud Run behavior.
Deployment work must resolve ephemeral SQLite state, proxy identity, supply-chain
signing/provenance, default-deny egress and durable audit before a release.

## Next GCP implementation slice

- Add an explicit Cloud Run entrypoint with a signed-IAP ASGI boundary. Require
  the configured service audience and one owner email. Verify ES256 signature,
  issuer, audience, lifetime and subject against Google's fixed IAP key endpoint.
  Reject missing, duplicate, malformed and forged assertions before application
  handlers, including queue/stream paths. Only a content-free GET health route
  is exempt. Preserve the normal local entrypoint; refuse it under Cloud Run.
- Use the verified, pseudonymous subject for abuse controls and Gradio's external
  authentication dependency. Plain email/forwarded headers are never identity.
  This owner-only slice does not claim multi-user or persistent-state readiness.
- Add release-image SBOM and vulnerability checks with immutable tooling inputs,
  detection controls and fail-closed evidence validation. Do not publish unsigned
  or unreviewed artifacts, or treat local scan results as deployed verification.
- Prepare infrastructure and cost controls for a USD 10 monthly demo budget;
  keep account identifiers private. All invitations remain separately gated.
