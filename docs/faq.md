# CRA2 review FAQ

## Questions a reviewer asks

### Does a low result approve a deployment?

No. Levels map to review routes: `low` → `routine-review`, `medium` →
`focused-review`, `high` → `priority-review`. A route states how much attention
a reviewer should give. CRA2 never approves, rejects, blocks, merges, or
deploys. A person or a separate organizational process decides next.

### What happens when my question is too vague?

CRA2 asks a clarifying question instead of scoring. No risk claim, no model
call.

Either a named unknown service or an unclear change triggers this. The
concreteness check is deterministic: it removes generic and service terms, then
requires at least two informative terms to remain. It does not catch every vague
or contradictory question.

### Does the catalog prove a freeze is active?

No. A reported active-freeze flag shows `unconfirmed` and adds a verification
question. It carries zero score weight and forces no high risk.

`not_reported` means the settings did not report a freeze. It does not prove no
freeze exists. The rest of the change is still assessed. Live calendar sync and
freshness checks are not implemented.

### What if my question conflicts with team settings?

It cannot. Precedence is catalog/default → request → team policy, and team
values win, including an explicit `false`. Typed text never overrides team
policy.

The result carries effective values, source evidence, and request/team
conflicts. The bundled `sample-team` policy marks `auth-service` as
`high_risk`, giving it a medium minimum. `CRA2_TEAM_SETTINGS_FILE` selects a
replacement file. This is local configuration, not user identity, a tenant
boundary, or an IAM system.

### Why is an incident from another service included?

Cross-service candidates need at least two meaningful shared terms with your
question. A matching change type alone does not qualify. At most five records
are selected, same-service history first.

External matches are labeled `cross_service_analogue`, with source dataset and
matched terms visible in the evidence panel. They never create a same-service
repeat penalty and never imply shared causation.

A valid citation proves the passage exists in what was retrieved. It does not
prove the model interpreted it correctly.

## Questions an operator asks

### What data reaches Groq, and how are credentials handled?

**Groq assessment** sends your question, the retrieved passages, and configured
policy facts to Groq. **Local evidence only** makes no network request at all.

Put the credential in the environment or in an explicitly selected dotenv file.
Guards reject exact known configured or SDK-held key values from checked input,
model payloads, returned text and metadata, and cache flows. Provider exceptions
detach from their original chains. Groq and HTTP-client namespace logs are
suppressed to limit debug-header and body exposure.

These controls do not detect every unknown, encoded, or transformed secret, and
they do not control caller-written logs, process-memory inspection, or provider
retention. Never paste credentials into the chat.

### Will I get identical results twice?

**Local evidence only** is deterministic: same question, same passages, every
run.

**Groq assessment** is best effort. Temperature zero, a fixed seed, a selected
model, and a strict JSON schema reduce variation without guaranteeing identical
wording. A bounded in-process cache reuses a recent answer, so a repeated
question may skip the provider entirely.

There is no durable history. The app does not restore conversations after a
refresh and does not persist team preferences across sessions.

### Is CRA2 ready as a hosted operational service?

No. This is a local chat app with a static sample catalog, bounded retrieval,
and optional Groq review.

Not implemented: hosting, authenticated multiuser access, IAM authorization,
managed ingress/egress, live catalog or policy freshness, postmortem ingestion,
and multiuser reproducibility controls. [architecture.md](architecture.md)
describes the current boundary. The
[policy evaluation](evidence/evals-policy-fast.md) checks synthetic
calibration cases offline; it establishes neither production accuracy nor
hosted security.