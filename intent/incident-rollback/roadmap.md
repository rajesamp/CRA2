# DevOps evidence and recovery roadmap

Researched 2026-11-20. Delivery order comes from the owner's request: finish Version 1, then start incident and rollback features. Invitations remain on hold.

## Market capabilities already documented

BMC Helix and Digital.ai are distinct products. These are vendor CAPABILITY claims, not a measured comparison with CRA and not evidence that CRA is superior.

| Product | Documented capability | Primary source |
| --- | --- | --- |
| BMC Helix Change Risk Advisor | Historical change outcomes, service health and dependency complexity inform risk; factor explanations, mitigations, what-if modeling and human oversight. | https://www.helixops.ai/products/agents/change-risk-advisor.html |
| Digital.ai Intelligence | Change failure probability with contributing features and model identifiers; historical and contextual analysis. | https://docs.digital.ai/platform/docs/analytics/data-api |
| Digital.ai Release | Risk prediction tasks and thresholds that can gate a release pipeline. | https://docs.digital.ai/release/docs/how-to/change-and-risk-prediction-plugin |

Generic history-based risk scoring and dependency awareness are established capabilities. The candidate CRA value proposition is a compact, inspectable DevOps review: **what could fail, what a rollback would leave behind, which evidence supports that conclusion, and what to test next**. This is a product hypothesis, not a claim of market-first functionality or demonstrated advantage.

## First implementation slice: incident and rollback workspace

Use the existing 46 bundled incident records (16 synthetic and 30 sanitized samples) and eight-service synthetic dependency snapshot. Preserve source labels, IDs, dates and match reasons. Distinguish same-service records from cross-service analogues. Do not derive failure probability or change failure rate from an incident-only corpus: the successful-change denominator is absent.

Add a protected, read-only workspace showing related history, recorded rollback approach, caller exposure, dependencies to check, structured rollback blockers and missing evidence. Compatibility, recovery rehearsal and side-effect reconciliation start as unknown. User answers are unverified declarations; a populated form cannot authorize rollback or prove readiness. No deployment, restore, deletion, invitation or dataset mutation action is exposed.

Acceptance: corrupt/unavailable sources fail closed; no match is not low risk; graph traversal handles cycles and preserves direction; schema incompatibility and unreconciled effects remain visible; source text cannot execute markup or instructions; credentials are rejected without echo; no external model request occurs. CI covers the new module and UI alongside existing identity isolation and abuse tests.

## Subsequent slices

1. **Approved incident ingestion.** Establish source ownership, service mappings, timestamps, incident/change links and successful-change denominator. Quarantine uploads, scan/redact sensitive fields, validate schemas and duplicates, test adversarial text, then require a human promotion decision. Store immutable source snapshots and attribution. V2 file upload enters this same quarantine, never the live training/evaluation corpus directly.
2. **Recovery evidence.** Connect artifact/config/schema diffs and rehearsal results. Analyze old-binary/new-schema and event-consumer compatibility, backup restore age, irreversible writes, duplicate side effects and reconciliation burden. Show rollback and roll-forward prerequisites; a human decides. Never present estimated recovery time as measured without a rehearsal record.
3. **Dynamic dependency visualization.** Show caller and dependency directions, selected change exposure, edge provenance and observation age. Missing/stale edges remain explicit. Concurrent changes can surface shared dependency contention. The V3 dataset bucket view shows dataset title, version, lineage, freshness and promotion status; the visual bucket is not a public storage endpoint.
4. **Deployment-note language signals.** Surface ambiguity, uncertainty and missing operational commitments with quoted spans. Sentiment is a secondary writing/review cue, never a stand-alone risk score or assessment of a person. Evaluate negation, sarcasm, technical shorthand and multilingual notes before adding an NLP model.
5. **Gamified peer reviews.** Reward reproducible failure modes, useful test evidence and post-incident learning. Evaluate team-level participation and accepted findings; avoid rewards for fast approvals, raw review volume or individual reliability rankings. Credits never grant deployment permissions.

## Differentiation experiments

- **Recovery boundary:** can reviewers identify a state change that an image rollback will not reverse? Measure recall of seeded irreversible migration, emitted event, issued token and payment side-effect cases.
- **Next missing experiment:** suggest the smallest check tied to the actual failure mechanism (for example mixed-version schema replay or timeout/retry load test). Measure whether the check resolves an explicitly recorded uncertainty.
- **Evidence freshness:** separate current measurements, historical facts, user declarations and unknowns. Measure unsupported current-state and causal claims; those should fail the evaluation.
- **Coupled release exposure:** correlate concurrent changes with shared callers, retry budgets, queues and connection pools. Start with recorded scenarios before connecting live telemetry.

Novelty and usefulness remain unproven. A later comparative decision should pin its own HERMETIC manifest and use the same seeded review cases and priorities for each candidate.

## DevOps signal contract and evaluation

For each signal retain value, unit, source ID, observed time, change window, service scope, freshness and missingness. Candidate signals: canary error/latency and SLO burn, retry amplification, queue lag, pool saturation, changed-interface test evidence, schema compatibility, deployment concurrency, rollback rehearsal age and duration, config drift, artifact provenance, incident recurrence and confirmed incident/change linkage.

Evaluate temporal holdouts and separate service families when labeled outcomes become available. Fit preprocessing only on training data; keep all later splits isolated. Report high-severity miss rate, false blocks, calibration (only if predicting probabilities), retrieval precision, source attribution, unknown handling, p95 latency and operational cost. Keep reserved adversarial cases out of feature tuning. Model sentiment and outcome predictors are not part of the initial deterministic slice.

For 1,000 accounts, separately test peak concurrent sessions and review arrival rate. The current single-instance app, process-local presence/queues and concurrency cap are demo boundaries, not a 1,000-active-user capacity guarantee. Shared presence and distributed work/state require explicit scaling work before expanding admission.
