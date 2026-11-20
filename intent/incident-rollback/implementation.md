# First slice implementation

`week2.incident_rollback` reuses the validated snapshot and deterministic incident
selector. It bounds source sizes/counts, preserves source IDs and matching terms,
excludes future dates and derives cycle-safe incoming/outgoing graph reachability.
Graph reachability is potential exposure, not measured production impact.

The new Gradio tab uses the existing verified-identity callback and `AbuseGate`.
Credentials and protected-action attempts are audited and blocked before source
retrieval. The analysis engine has no provider or execution client. Results are
escaped HTML; raw execution JSON remains absent from the UI. No form data is
promoted to the dataset or stored as a shared review.

Compatibility and rehearsal failures, plus untested reconciliation, appear as
reported blockers. Unknown answers and absent plans produce specific next checks.
All answers remain unverified; freshness and independent verification are always
open gaps. Even all-Pass answers cannot authorize an action. Recorded rollback
timings are not treated as measured recovery estimates.

The existing Week 2–4 CI matrix discovers the new tests automatically. Container
verification also exercises the engine with networking disabled and records the
new module's source hash. The deployed Version 1 release remains separate from
this prototype until a subsequent release completes its gates.

Limitations: bundled historical corpus only, static dependency edges, no actual
recovery rehearsal, no live incident connector, no failure probability and no
automatic rollback. The proposed rollback text helps retrieval and detects a
missing plan; this slice does not semantically validate its completeness.
