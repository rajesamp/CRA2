# CRA2 review: corrections and feature candidates

Reviewed 2026-11-22 at `de338ae3fa4650fa8153850edf47f1402ec4051d`.
Scope: targeted code/document review, four real NeMo context probes, app queue
construction, current PR/CI metadata and read-only live service configuration.
This is not a full penetration test, new load test, browser acceptance or a fresh
run of the entire test suite. The prior green CI result was re-read, not rerun.

## Baseline and limits

| Surface | Observed state | Evidence |
|---|---|---|
| Live app | Ready; IAP enabled; matches the existing V1 image record; no extra app-allowlist accounts; one maximum instance and concurrency four | [Sanitized live observation](live-baseline.json); inherited IAM and browser login not retested |
| Candidate | PRs [29](https://github.com/rajesamp/CRA2/pull/29), [30](https://github.com/rajesamp/CRA2/pull/30), [31](https://github.com/rajesamp/CRA2/pull/31) remain draft/open; latest guardrail/eval candidate has four successful workflows | [CI run](https://github.com/rajesamp/CRA2/actions/runs/44761690657), [container gate](https://github.com/rajesamp/CRA2/actions/runs/44761691206) |
| Runtime | Gradio/FastAPI, LangGraph, two read-only MCP tools, local BGE/ONNX retrieval, NeMo 0.24.1 custom actions, GCP persistence/IAP | [app](https://github.com/rajesamp/CRA2/blob/de338ae3fa4650fa8153850edf47f1402ec4051d/week2/cloud_app.py), [workflow](https://github.com/rajesamp/CRA2/blob/de338ae3fa4650fa8153850edf47f1402ec4051d/week2/workflow.py), [tool contracts](https://github.com/rajesamp/CRA2/blob/de338ae3fa4650fa8153850edf47f1402ec4051d/week2/contracts.py) |
| Evaluation | TruLens Feedback 2.16.0 in CI, outside the app image; six same-author source-backed ID-retrieval cases | [labels](https://github.com/rajesamp/CRA2/blob/de338ae3fa4650fa8153850edf47f1402ec4051d/evaluation/retrieval-cases-v1.json), [scorer](https://github.com/rajesamp/CRA2/blob/de338ae3fa4650fa8153850edf47f1402ec4051d/evaluation/score.py) |
| Data/recovery | 46 bundled incident records; static eight-service graph; no successful-change denominator; rollback declarations unverified | [analysis](https://github.com/rajesamp/CRA2/blob/de338ae3fa4650fa8153850edf47f1402ec4051d/week2/incident_rollback.py), [roadmap](https://github.com/rajesamp/CRA2/blob/de338ae3fa4650fa8153850edf47f1402ec4051d/intent/incident-rollback/roadmap.md) |
| Durable execution | Preferences/audit persist; the LangGraph workflow compiles without a checkpointer; no implemented UTCP adapter | [workflow](https://github.com/rajesamp/CRA2/blob/de338ae3fa4650fa8153850edf47f1402ec4051d/week2/workflow.py#L480); code/dependency inventory |

The earlier 459 tests per supported application Python version, 14 evaluator
tests, 22 contract cases and nine fault checks remain valid evidence for their
tested scope. New context probes expose cases that suite did not cover.

## Corrections and release gates

“Important” means a behavior, evidence or policy gap. Sequencing below is a
proposed gate, not an accepted schedule. No P0 compromise is established.

### C1 — Important: context injection variants are accepted

**Confirmed behavior.** The actual NeMo context action blocks the canonical
phrase but allows a newline variant and a zero-width variant. The benign control
is allowed: two expected results and two misses across four probes.
[Probe evidence](context-probes.json); [pattern and context action](https://github.com/rajesamp/CRA2/blob/de338ae3fa4650fa8153850edf47f1402ec4051d/week3/guardrails.py#L24).

**Implication.** The context filter cannot support a broad injection-resistance
claim. Current tools are read-only and the UI is non-generative; this probe does
not demonstrate data exfiltration, execution or an end-to-end compromise.

**Correction intent.** Define and normalize equivalent text representations at
the trust boundary, preserve inert source display, and add adversarial variants
plus benign quotation/technical-document controls. Keep structural tool policy
independent of the content detector. Normalize carefully: stripping characters
must not silently change identifiers or the evidence shown to the reviewer.

**Done when.** Failing regression cases reproduce first; the repaired boundary
blocks those variants before protected use, benign controls remain accepted,
unavailable checks fail closed, and false blocks/misses have explicit denominators.
Gate before accepting new untrusted uploads or enabling generative use.

### C2 — Important: bounded capacity is not enforced end to end

**Confirmed behavior.** Constructing the candidate app exposes an unlimited
Gradio pending-queue size and default concurrency one. Cloud Run is capped at
one instance/four requests. Presence and security cooldowns are process-local.
[Queue probe](queue-probe.json), [app wiring](https://github.com/rajesamp/CRA2/blob/de338ae3fa4650fa8153850edf47f1402ec4051d/week2/app.py#L367),
[cooldowns](https://github.com/rajesamp/CRA2/blob/de338ae3fa4650fa8153850edf47f1402ec4051d/week2/abuse.py#L110), [presence](https://github.com/rajesamp/CRA2/blob/de338ae3fa4650fa8153850edf47f1402ec4051d/week2/presence.py).

**Correction intent.** Define bounded pending work and per-principal request
quotas, including direct API paths; return a useful busy/retry state. Test stream
connections, cancellations and reconnects. Make quotas/cooldowns durable across
instances before horizontal scaling; define presence as recent activity rather
than Google login truth. Treat registered accounts, daily active users and
concurrent reviews as different quantities.

**Done when.** A declared concurrency/arrival-rate workload meets owner-approved
p95/error and cost targets; excess work is rejected predictably; restart/two-
instance tests preserve isolation and quotas. Include IAP, admission, queue time,
idle browser streams, storage/network costs and the public intro in measurements.
No 1,000-user readiness claim before that evidence. Current billing enforcement
and all-service spend still require inspection; [budget](https://github.com/rajesamp/CRA2/blob/de338ae3fa4650fa8153850edf47f1402ec4051d/docs/cloud-run-budget.md)
is a planning model, not a verified total bill.

### C3 — Important: retrieval scores are narrower than product quality

**Confirmed gap.** All six TruLens cases are same-author development regressions.
Labels pair an incident with its derived postmortem; minimum per-case recall is
0.5. The scorer explicitly reports semantic faithfulness and jailbreak resistance
as not measured. [Cases](https://github.com/rajesamp/CRA2/blob/de338ae3fa4650fa8153850edf47f1402ec4051d/evaluation/retrieval-cases-v1.json),
[scorer](https://github.com/rajesamp/CRA2/blob/de338ae3fa4650fa8153850edf47f1402ec4051d/evaluation/score.py#L96).

**Correction intent.** Keep the existing gate, then add independently reviewed
cases for wrong-service analogues, unsupported causal claims, stale evidence,
ambiguous changes, no evidence, conflicting sources and recovery side effects.
Freeze splits by incident family and, when real outcomes exist, time/service to
avoid the incident/postmortem pair leaking across training and holdout sets.
Measure source entailment, claim support, critical misses, false blocks, unknown
handling and end-to-end latency separately from retrieval ID overlap.

**Done when.** Labels, thresholds and denominators are frozen before results;
held-out cases are not used for tuning; independent reviewers adjudicate disputed
labels; degraded evidence and overconfident answers fail negative controls.
A semantic LLM judge needs an approved model/data/budget boundary and agreement
against human labels. An external judge is not needed to start human evaluation.

### C4 — Important: audit completion/correlation is incomplete

**Confirmed in application code.** Preference writes append a durable
`memory_write_requested` event before mutation; the application path does not
append a correlated committed/failed result. Recovery NeMo events are returned
to session state but do not go through the chat telemetry writer.
[Preference writes](https://github.com/rajesamp/CRA2/blob/de338ae3fa4650fa8153850edf47f1402ec4051d/week2/cloud_storage.py#L221),
[recovery boundary](https://github.com/rajesamp/CRA2/blob/de338ae3fa4650fa8153850edf47f1402ec4051d/week2/incident_rollback.py#L154),
[telemetry projection](https://github.com/rajesamp/CRA2/blob/de338ae3fa4650fa8153850edf47f1402ec4051d/week4/telemetry.py#L19).

**Correction intent.** Define a metadata-only assessment/event ID and record
attempt/result state for durable changes, plus coverage facts for recovery checks.
Model the partial-failure case explicitly: a successful write followed by audit
failure must not be reported as a rolled-back write. Use an idempotent event or
outbox design only after the failure contract is agreed.

**Done when.** Restart/retry and storage-failure tests can reconstruct whether a
mutation committed without raw prompts or identity disclosure. Preserve the
existing locked retention and current-session-only UI. This is an application
audit finding; GCP platform audit coverage was not inventoried here.

### C5 — Important: live/draft and SDLC status need one release record

**Confirmed gap.** Live V1 differs from the incident/guardrail draft stack.
The two latest feature directories contain spec/implementation records but no
`intent.md`/`plan.md` pair. Earlier user authorization is not being disputed;
the newly invoked artifact-chain convention must apply prospectively.

**Correction intent.** Inventory what is live, accepted, draft and planned with
commit, image, dataset and evaluation versions; resolve the PR stack in review
order. Add a concise version/evidence label to the app. Rebuild/reverify release
evidence and perform owner acceptance before inviting users. Store reproducible
launch instructions and persistent artifact links; temporary localhost previews
and deleted `/tmp` checkouts are not durable release evidence.

**Done when.** Each new slice has accepted intent/spec, a plan that travels with
code, linked regression evidence and an owner decision. Never retroactively mark
old artifacts accepted or merge them automatically. Review/accept this Stage 1
artifact before its commit and before Stage 2 begins.

### C6 — Important documentation/UX correction: describe the deployed contract

**Confirmed mismatch.** The architecture overview tells users to pick Groq in
the UI and says local mode has “No network”; the protected app fixes the mode to
local evidence and uses networked identity/storage. Legacy CLI/local capabilities
should remain documented separately. The cooldown banner asserts “Adversary
actions noted”, while the new panel correctly says a match is not proof of intent.
[Overview](https://github.com/rajesamp/CRA2/blob/de338ae3fa4650fa8153850edf47f1402ec4051d/docs/architecture-overview.md#L104),
[current app](https://github.com/rajesamp/CRA2/blob/de338ae3fa4650fa8153850edf47f1402ec4051d/week2/app.py#L324), [banner](https://github.com/rajesamp/CRA2/blob/de338ae3fa4650fa8153850edf47f1402ec4051d/week2/app.py#L235).

**Done when.** Cloud UI/help/docs agree on available modes and data destinations;
no generative LLM is distinguished from no network; static evidence is clearly
dated; wording says a security condition matched without assigning intent.
Add a review check that current UI capabilities match the published feature list.

## Feature cards

Candidate value proposition to validate: **show what can fail, what reversal
cannot restore, what evidence is missing, and the smallest useful next test.**
This is a hypothesis, not a claim of novelty or superiority.

| ID / candidate | User value and first usable slice | Prerequisite / completion evidence |
|---|---|---|
| F1 Recovery boundary map | Show which schema, data, event, token, payment and config effects survive an image rollback. Compare rollback and roll-forward prerequisites without executing either. | Extend the existing prototype using artifact/schema diffs and signed or attributable rehearsal records. Seed irreversible-migration, mixed-version, duplicated-event and reconciliation scenarios; detect every seeded critical gap; unknowns remain unknown. |
| F2 Versioned review evidence bundle | One review ID links the change, artifact digest, dataset version, source citations, signal ages, guardrail coverage, unresolved checks and human decision. Export a redacted review packet and compare two revisions. | C4/C5; each material claim points to a source/version; no raw security prompt, full account address or private infrastructure identifier in shared exports. |
| F3 Incident-to-change learning | Link changes to incidents, near misses and successful deployments. Separate same-mechanism recurrences from textual resemblance. | Explicit source owner and permissions; stable service IDs, source time, outcome adjudication and successful-change denominator. Validate temporal/service holdouts before any probability claim. |
| F4 DevOps signal panel | Show canary error/latency deltas, SLO burn, retry amplification, queue lag, connection-pool pressure, config drift and artifact provenance, with source/time/unknown labels. | Begin with one read-only approved connector and recorded fixtures; stale or missing signals cannot become green. Correlate by change window without claiming causation. |
| F5 Dependency and concurrent-change graph | Visualize callers versus dependencies, edge provenance/age and the proposed change. Surface simultaneous schema/config changes competing for shared resources. | Versioned graph input, missing-edge state and cycle bounds; seeded caller impact and shared dependency cases. A stale snapshot must never be labelled live. |
| F6 V2 quarantined change upload | Parse an allowlisted bounded file; show redaction, validation and adversarial findings; let a human promote an approved snapshot into a versioned corpus. | C1–C4; sandbox/time/memory limits, per-user namespaces, duplicate handling, malicious-file controls and no automatic promotion. Training/reference/holdout data must remain separate. |
| F7 V3 dataset explorer | Bucket illustration with the selected dataset title, version, provenance, freshness, counts and promotion status. Inspect records and changes between versions. | F6 manifest contract; the illustration is not a public bucket URL; explicit unavailable/empty states and reduced-motion support. |
| F8 Deployment-note quality cues | Highlight missing owner, rollback trigger, monitoring or ambiguous statements with the supporting text span. Sentiment is a secondary cue. | Experiment with reviewer-labelled negation, technical shorthand and multilingual cases. Measure useful findings and false alarms; never rate a person's reliability from tone. |
| F9 Evidence-based peer-review challenges | Reward accepted failure hypotheses, reproducible tests and useful post-incident corrections. Preserve disagreement and reviewer attribution. | Invite approval and reviewer roles first; no points for rapid approvals or raw volume; no score grants deployment permission. Pilot measures review usefulness, not an individual risk ranking. |
| F10 Durable review execution | Resume an interrupted long-running ingestion/review, preserve policy/data versions and make retries idempotent. | Only after a workflow needs it; restart mid-step, expired approval, duplicate callback and cancellation tests. Durable preferences alone are not durable graph execution. |
| F11 UTCP adapter experiment | Call one approved read-only source through UTCP while preserving the existing host contract, schema validation, identity and egress boundary. | Same frozen scenarios through current MCP and candidate UTCP adapters; compare completeness, errors, cancellation, latency and denied calls. No protocol winner or rewrite is established. |

## Product and architecture evidence

- BMC Helix documents historical outcomes, health/dependency signals, factor
  explanations and what-if analysis. Those are vendor **CAPABILITY** claims;
  they establish existing market functionality, not comparative performance.
  [Official overview](https://www.helixops.ai/products/agents/change-risk-advisor.html).
- Digital.ai Release documents risk prediction and a risk prediction gate.
  [Official plugin documentation](https://docs.digital.ai/release/docs/how-to/change-and-risk-prediction-plugin).
  CRA2 differentiation therefore needs a measured reviewer-benefit experiment,
  not just a generic risk score or a claim to be first.
- LangGraph documents persistent checkpoints as the basis for resumable state.
  CRA2 currently calls `compile()` without one. An “agent substrate” is treated
  here as a proposed execution capability, not an installed product.
  [Official persistence documentation](https://docs.langchain.com/oss/python/langgraph/persistence).
- UTCP documents discovery/calling across HTTP, CLI, WebSocket and MCP plugins.
  That is a transport capability, not evidence that authorization or injection
  defenses improve. [Official specification](https://github.com/universal-tool-calling-protocol/utcp-specification).

## Acceptance and flagged concerns

This review proposes work; it does not implement it. The owner must accept the
intent before design, and accept the design/plan before product code changes.
Unresolved: first real source and data steward, peak workload/SLO, total budget,
independent label reviewer, semantic-judge permission and exact substrate scope.

The parent policy references a `sentinel-mcp-tool-poisoning` skill that was not
found in the two local skill roots searched. Keep the existing closed two-tool
contract, and resolve the missing policy mapping before broad tool discovery.
No rule file or this document proves runtime interception.
