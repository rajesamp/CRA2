# Spec: SAC P0/P1

Source: accepted issue #19 and the explicit P0/P1 implementation request.
Status: authorized implementation scope; draft for PR review.

## Requirements
1. Optional instrumentation leaves normal answers, traces and routing unchanged.
2. Baseline reports identify source revision, fixture/config identity, observed
   timing, actions, tool/provider activity, failures and missing usage.
3. Semantic state is closed, versioned, bounded, canonical JSON with no raw
   outputs, policy values, operational claims, or approval decisions.
4. External authority binds objective, service, policy references, evidence
   provenance, action order and validated results. State cannot create authority.
5. Reduction is pure and deterministic; malformed state, unknown references,
   conflicts, stale policy identity, and overflow raise protected errors.
6. Replay/adversarial tests and existing offline gates provide review evidence.

## Design
Use the existing JSON-schema contract style and credential guards. A host-owned
context retains source digests and validated action records outside compact
state. State stores references and a provenance digest; validation replays the
referenced prefix against that external ledger. Evidence and unresolved-question
references accumulate without silent dropping. Policy identity is immutable for
one execution; a changed policy requires a new execution.

## Policy conformance
`CLAUDE.md`, `week2/contracts.py`, `week2/preferences.py`, and the existing citation
gates remain authoritative. The reducer neither executes tools nor renders risk
assessments. The normal workflow does not consume semantic state in this phase.

## Flagged concerns
An external ledger must come from host validation, never model-supplied metadata.
Hashes identify content; they are not signatures or independent proof of truth.
P2 must wire actual tool/provider adapters and a bounded execution loop before
any production or efficiency claim is valid.
