# CRA2 review FAQ

## Questions a reviewer asks

### Does a low result approve a deployment?

No. Levels map to review routes: `low` → `routine-review`, `medium` →
`focused-review`, `high` → `priority-review`. A route states how much attention
a reviewer should give. CRA2 never approves, rejects, blocks, merges, or
deploys. A person or a separate organizational process decides next.

### What happens when the request is too vague?

CRA2 returns `status: "needs_clarification"` plus targeted questions. Risk,
score, and route stay null, and no model is called.

A missing or unknown service or change type triggers this, as does a
missing or generic summary. The summary check is a deterministic heuristic: it
removes generic and service/type terms, then requires at least two informative
terms to remain. It does not catch every vague or contradictory request.

Malformed JSON and invalid field types are reported as input errors instead.

### Does the catalog prove a freeze is active?

No. An effective active-freeze flag yields `freeze.status: "unconfirmed"` and
a verification question. It carries zero score weight and forces no high risk.

`not_reported` means the settings did not report a freeze. It does not prove
no freeze exists. The rest of an assessable change is still reviewed. Live
calendar sync and freshness checks are not implemented.

### What if a request conflicts with team settings?

Precedence is catalog/default → request → team policy. Team values win,
including an explicit `false`.

The result carries effective values, source evidence, and request/team
conflicts. The bundled `sample-team` policy marks `auth-service` as
`high_risk`, giving it a medium minimum. `CRA2_TEAM_SETTINGS_FILE` selects a
replacement file. This is local configuration, not user identity, a tenant
boundary, or an IAM system.

### Why is an incident from another service included?

Cross-service candidates need at least two meaningful shared terms with the
change. A matching change type alone does not qualify. At most five records
are selected, same-service history first.

External matches are labeled `cross_service_analogue`, with source dataset and
matched terms visible in `incident_context`. They never create a same-service
repeat penalty and never imply shared causation.

A valid citation proves membership in supplied context. It does not prove the
model interpreted the fact correctly.

## Questions an operator asks

### What data reaches Groq, and how are credentials handled?

`auto` and `deep` send normalized change details, catalog and settings context,
and selected incidents to Groq. The user authorized the 30 sanitized samples
for public distribution and this provider context. The original 16 incidents
stay synthetic. `fast` stays local, and clarification makes no provider call.

Put the credential in the environment or in an explicitly selected dotenv
file. Guards reject exact known configured or SDK-held key values from checked
input, model payloads, returned text and metadata, and cache flows. Provider
exceptions detach from their original chains. Groq and HTTP-client namespace
logs are suppressed to limit debug-header and body exposure. Requests use the
fixed Groq API endpoint.

These controls do not detect every unknown, encoded, or transformed secret,
and they do not control caller-written logs, process-memory inspection, or
provider retention. Never put credentials in change content.

### Will two users get identical results?

Local rules are deterministic for the same normalized input, catalog,
incidents, and team policy. Timings differ.

Comparing runs requires shared policy and data versions. A model ID and a seed
do not guarantee the same fresh Groq answer. The bounded in-memory cache
belongs to one process; it provides neither durable history nor cross-user
consistency.

Eval repeatability checks status, score, level, route, comments, questions,
freeze state, settings, and conflicts. That is evidence for one run, not a
universal guarantee.

### Is CRA2 ready as a hosted operational service?

No. The repository is a local CLI and library with a static sample catalog,
bounded incident retrieval, and optional Groq review.

Not implemented: hosting, authenticated multiuser access, IAM authorization,
managed ingress/egress, live catalog or policy freshness, postmortem ingestion,
and multiuser reproducibility controls. [architecture.md](architecture.md)
describes the current boundary. The
[policy evaluation](evidence/evals-policy-fast.md) checks synthetic
calibration cases offline; it establishes neither production accuracy nor
hosted security.