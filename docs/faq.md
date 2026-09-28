# CRA2 review FAQ

## Customer questions

### 1. Does a low result approve a deployment?

No. Low, medium, and high map to `routine-review`, `focused-review`, and
`priority-review`. They describe attention required from a reviewer. CRA2 never
approves, rejects, blocks, merges, or deploys a change. A human or a separately
implemented organizational process decides what happens next.

### 2. What happens when the request is too vague?

A missing or unknown service/change type, or a missing/generic summary, produces
`status: "needs_clarification"` and targeted questions. Risk, score, and route
are null, and no model request is made. A deterministic summary heuristic asks
for more detail when fewer than two informative terms remain after generic and
service/type terms are removed. It does not catch every vague or contradictory
request. Malformed JSON and invalid field types are reported as input errors.

### 3. Does the catalog prove that a freeze is active?

No. An effective active-freeze flag yields `freeze.status: "unconfirmed"` and a
verification question. It carries zero score weight and does not force high
risk. `not_reported` means the settings did not report an active freeze; it does
not prove there is no freeze. The rest of an assessable change is still reviewed.
Live calendar synchronization and freshness checks are not implemented.

### 4. What if a request conflicts with team settings?

Settings resolve from catalog/default values to request values, then explicit
team policy. Team values win, including an explicit `false`. The result includes
effective values, source evidence, and request/team conflicts. The bundled
`sample-team` policy marks `auth-service` as `high_risk`, giving it a medium
minimum. `CRA2_TEAM_SETTINGS_FILE` selects a replacement policy file. This local
configuration is not a user identity, tenant boundary, or IAM system.

### 5. Why is an incident from another service included?

Cross-service candidates must share at least two meaningful terms with the
change; matching the change type alone is insufficient. At most five records
are selected, with same-service history ranked first. External matches are
labeled `cross_service_analogue`, with source dataset and matched terms visible
in `incident_context`. They never create a same-service repeat penalty or imply
shared causation. A valid citation verifies membership in supplied context,
not the truth of the model's interpretation.

## Internal questions

### 6. What data can reach Groq, and how are credentials handled?

`auto` and `deep` can send normalized change details, catalog and setting context,
and selected incidents. The user authorized the 30 sanitized samples for public
GitHub distribution and this provider context; the original 16 incident fixtures
remain synthetic. `fast` stays local, and clarification makes no provider call.

The configured credential belongs in the environment or an explicitly selected
dotenv file. Application guards reject exact known configured/SDK-held key values
from checked input, model payloads, returned text/metadata, and cache flows.
Provider exceptions are detached from their original chains, and Groq/HTTP-client
namespace logs are suppressed to limit debug-header/body exposure. Requests use
the fixed Groq API endpoint. These controls do not detect every unknown, encoded,
or transformed secret and do not control caller-written logs, process-memory
inspection, or provider retention. Do not put credentials into change content.

### 7. Will two users always get identical results?

Local rules are deterministic for the same normalized input, catalog, incident
collection, and team policy. Time measurements differ. Shared policy/data
versions are needed to compare runs; a model ID and seed do not guarantee the
same fresh Groq answer. The bounded in-memory cache belongs to one process and
provides neither durable history nor cross-user consistency. Eval repeatability
checks status, score, level, route, comments, questions, freeze state, settings,
and conflicts. It is evidence for that run, not a universal guarantee.

### 8. Is CRA2 ready as a hosted operational service?

The repository implements a local CLI/library, static sample catalog, bounded
incident retrieval, and optional Groq review. Hosting, authenticated multiuser
access, IAM authorization, managed ingress/egress, live catalog/policy freshness,
postmortem ingestion, and multiuser reproducibility controls are not implemented.
The [architecture](architecture.md) describes the current boundary. The
[policy evaluation](evidence/evals-policy-fast.md) checks synthetic calibration
cases offline; it does not establish production accuracy or hosted security.
