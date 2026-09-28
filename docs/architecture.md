# CRA2 architecture

CRA2 is a synchronous Python library and CLI over a static, synthetic checkout
system. It validates a structured change, computes a rule score, optionally
requests a Groq assessment, applies risk floors, and returns three comments.
It performs no deployment, approval, blocking, or repository mutation.
Incomplete intent returns clarification questions without a risk assessment or
provider request. All routes describe review attention, never a ship decision.
Incident context combines 16 original synthetic records with 30 sanitized
user-provided samples. The external samples retain their original labels and
provenance; they do not expand the synthetic service catalog.

## Pipeline

```mermaid
flowchart TD
    Input[Structured change] --> Validate[Validate and normalize]
    Validate --> Complete{Enough detail to assess?}
    Complete -- No --> Clarify[Targeted questions, no risk or provider call]
    Complete -- Yes --> Context[Catalog, team settings, dependencies, incidents]
    Context --> Rules[System 1 rules and initial level]
    Rules --> Select{Deep mode or auto and uncertain?}
    Select -- No --> Floor[Apply rule level and policy floors]
    Select -- Yes --> Cache{Validated response in cache?}
    Cache -- Yes --> Blend[Blend scores and combine comments]
    Cache -- No --> Groq[At most one Groq SDK request attempt]
    Groq --> ValidateResponse[Validate JSON and filter model comments]
    ValidateResponse -- Valid --> Blend
    Groq -- Unavailable --> Fallback[Retain System 1 and availability note]
    ValidateResponse -- Invalid --> Fallback
    Fallback --> Floor
    Blend --> Floor
    Floor --> Output[Level, route, three comments, advisory, telemetry]
```

| Component | Responsibility |
|---|---|
| `cra2/__main__.py` | Read a sample ID, UTF-8 JSON file, or stdin; report argument/input errors |
| `cra2/config.py` | Validate environment settings; opt in to a selected dotenv file; locate packaged/source resources |
| `cra2/advisor.py` | Input validation, context, selection gate, risk floors, comment ordering, results, rendering |
| `cra2/incidents.py` | Load and validate both incident sources; rank and annotate up to five related records |
| `cra2/team_settings.py` | Validate team/request booleans, resolve precedence, and expose effective sources/conflicts |
| `cra2/system1.py` | Deterministic rule scoring and evidence-linked comment templates |
| `cra2/system2.py` | Groq request, response validation, output hygiene, usage accounting, bounded cache |
| `cra2/rules.json` | Thresholds, weights, route labels, and local comment wording |
| `scripts/run_evals.py` | Offline/live evaluation, all-repeat quality gate, scoped evidence report |

Canonical fixtures remain in `data/` and `evals/`. The wheel build maps them
into `cra2/data/` and `cra2/evals/`, respectively. Package execution does not
require a source checkout. The repository evaluation script reads its source
case file; it is not an installed command.

## Input and context

Assessable requests need a known `service`, a supported `change_type`, and a
concrete `summary`. Missing or unknown service/type and absent/generic summaries
return `status: "needs_clarification"` with targeted questions and null risk,
score, and route. No incident context or model request is produced. The summary
heuristic removes generic terms and service/type tokens and requires at least
two remaining distinct informative terms; it does not understand every vague
or contradictory request.

Optional fields are string `id`, the three plan strings (`deploy_plan`,
`rollback_plan`, `monitoring_plan`), and `settings`. An omitted or null plan
normalizes to an empty string. Settings accept only boolean
`freeze_window_active` and `high_risk`. Whitespace is trimmed; invalid types,
unknown fields, and strings over 10,000 characters are input errors before any
provider request. A request needing clarification is different from malformed
JSON or an invalid field type.
Fields reject Unicode category-C characters other than tabs, carriage returns,
and newlines. The CLI caps file/stdin input at 1,048,576 decoded Unicode
characters and rejects duplicate JSON keys and excessive nesting.

Context contains the service record, transitive reverse dependents, and at most
five incidents selected from the combined 46-record collection. A candidate
matches the exact service or shares at least two meaningful terms with the
change. Cross-service type matches alone are insufficient. Ranking prefers exact service,
with matching normalized type first within same-service history. Cross-service
candidates rank by greater informative token overlap, then matching normalized
type, then newer date with a stable incident-ID tie-break. Short technical terms
such as `OOM`, `CPU`, `CDN`, `ACL`, and `503` are retained. The only comparison
alias is `Deployment` → `Code deploy`;
stored labels remain unchanged. This local lexical retrieval uses no embeddings
or provider request.

Cross-service records provide analogous history. They cannot establish a
same-service repeat-incident signal, fabricate catalog facts, or create a new
service that the CLI accepts. Every external type, including deployment and
no-change categories, needs sufficient overlap to enter the candidate set. The collection
contains 28 external sample service labels; the catalog still has eight services.

The selected records are returned as `incident_context` and included in provider
context, capped at five. Each is annotated with `source_dataset` (`synthetic` or
`sanitized_samples`), `match_kind` (`same_service_history` or
`cross_service_analogue`), and `matched_terms`. The annotations explain selection
and provenance without asserting that analogous services share an incident.

The changed service and its direct outgoing dependencies are checked for degraded
health; this check is not recursive.
Graph traversal handles cycles without counting the changed service as its own
dependent. The static fixture is not live operational state.

The model receives the normalized change, primary and direct-dependency catalog
records, related incidents, dependent names, degraded names, allowed evidence
keys, and System 1 signals. A Groq request sends this context off the local
machine. `fast` mode never selects this path.
The user authorized the sanitized samples for public GitHub and provider context.
Adding them did not involve any live Groq calls.

## Team settings and freeze uncertainty

`data/team_settings.json` names the sample team and marks `auth-service` as
`high_risk`. `CRA2_TEAM_SETTINGS_FILE` can select a replacement JSON file;
unrelated files in the working directory are not discovered. Known catalog
services may configure only `freeze_window_active` and `high_risk` booleans.

Resolution is catalog/default → request settings → explicitly present team
settings. An explicit team `false` overrides request `true`. The result's
`settings` contains the team, effective booleans, and source evidence keys.
`settings_conflicts` lists request/team disagreements with field, requested
value, effective value, and source. This is process-level local policy, not
tenant identity or an authorization boundary.

An effective active freeze produces `freeze.status = "unconfirmed"`, the
reported-active flag, source evidence, and a verification question. Otherwise
the status is `not_reported`, which does not prove that a freeze is absent.
The freeze signal has zero score weight and imposes no risk floor. An assessment
can remain `assessed` while asking the reviewer to confirm freeze status.

## Scoring and policy floors

System 1 adds the change-type base, tier weight, up to 0.08 for transitive
reverse dependents (0.02 each), and applicable rule weights. The total is
capped at 1.0 and rounded to two decimals.

| Rule | Weight |
|---|---|
| Reported active freeze | 0; explicit unconfirmed status and verification question |
| Same-service incident with matching normalized type | 0.15 each, capped at 0.30; cross-service analogies add no repeat penalty |
| Missing rollback plan | 0.20 |
| Missing monitoring plan | 0.10 |
| Config change on a drift-prone service | 0.10 |
| Missing deploy plan on a service with dependents | 0.05 |
| Changed service or direct dependency degraded | 0.05 |

| Tier | Low | Medium | High |
|---|---|---|---|
| `critical` | score < 0.20 | 0.20 ≤ score < 0.50 | score ≥ 0.50 |
| `core` | score < 0.30 | 0.30 ≤ score < 0.60 | score ≥ 0.60 |
| `standard` | score < 0.40 | 0.40 ≤ score < 0.70 | score ≥ 0.70 |

Degraded health or effective `high_risk = true` forces at least medium. A freeze
report alone does not elevate risk. System 1 is uncertain when the minimum
distance between its score and a tier threshold, rounded to two decimals, is
**less than** 0.05.
Exactly 0.05 is outside the gate. An uncertain assessment is at least medium in
every mode, including `fast` and provider fallback.

System 2 rates five areas: deploy order, rollback, config drift, dependencies,
and monitoring. Ratings map to none=0, low=0.33, medium=0.67, high=1. Its score
is `0.6 × maximum + 0.4 × mean`, rounded to two decimals. A successful response
is blended equally with the System 1 score under the current rules.

The final level is the greater of the blended score's tier band and the risk
floor. That floor is at least the initial System 1 level. A benign model reply
therefore cannot reduce a rule-based medium/high result to low. The numeric
blended score can fall below the displayed level's threshold; `risk_floor` and
`system1_level` explain why. The route mapping is low → `routine-review`, medium →
`focused-review`, high → `priority-review`, always accompanied by an advisory
notice. None of these routes authorizes approval, rejection, or deployment.

## Provider contract and grounding limits

Requests use temperature zero, the configured integer seed, a model ID,
completion-token cap, strict JSON schema, and a finite timeout. The default
model uses low reasoning effort with reasoning excluded from the reply.
Automatic SDK retries are disabled. Cache hits and missing credentials can
mean no SDK request attempt at all.

Local validation rejects missing/extra response fields, invalid rating enums,
wrong types, oversized strings/arrays, duplicate JSON keys, nonfinite numbers,
empty choices, refusals, and incomplete completions. Provider schema support
is not trusted as the only validator. Expected provider/response failures are
wrapped as `System2Unavailable`, with usage retained when a response supplied it.
Programming errors outside this boundary are not silently treated as outages.

Comments with unknown evidence keys, disallowed execution/approval wording,
control characters, links, or markup are filtered. Surviving model comments
join rule comments in stable severity order; rule comments win equal-severity
ties. The first comment for each distinct tag is kept, up to three. Local
fallback comments fill missing areas. Human-readable rendering escapes untrusted
inline text and strips terminal control characters.

These checks establish structure and citation membership. They do not prove
that model prose is factual or that every prompt injection will be detected.
Risk floors constrain the model's authority independently of its wording.

Exact known configured/SDK-held API keys are rejected from checked inputs,
payloads, response text/metadata, and cache flows. Expected provider failures
detach their original exception chains. Groq/HTTP-client namespace logging is
suppressed to reduce debug-header/body exposure, and the client uses a fixed Groq
API endpoint. These are scoped application controls: they do not detect unknown,
encoded, or transformed secrets or govern caller logs, memory inspection, or
provider retention. Application cache storage is process-local memory only.

## Cache, repeatability, and telemetry

The process-local LRU cache holds up to 512 successful validated responses.
Cache identity includes serialized normalized context and request-affecting
model, seed, temperature, token cap, timeout, reasoning settings, prompt, and
schema. Failed replies are not cached. Cache data stays in memory until eviction,
explicit clearing, or process exit. Concurrent misses may each request the same
answer; the cache does not provide a single-flight guarantee.

System 1 results are deterministic for fixed input and policy data, excluding
timing. A cache hit reuses a validated model answer. Fresh Groq responses remain
best effort: sampling settings and schema do not guarantee identical text or
reasoning across requests or backend changes. Model IDs are not immutable
version pins, and fingerprints may be absent.

| Result field | Meaning |
|---|---|
| `status` | `assessed` or `needs_clarification`; clarification has null risk/score/route and no provider call |
| `questions` | Targeted clarification or freeze-verification questions; freeze questions may accompany assessed results |
| `freeze` | Reported-active status, explicit uncertainty, and source evidence; null for clarification |
| `settings` / `settings_conflicts` | Effective policy and provenance, plus request/team disagreements |
| `path` | `system2`, `system1`, or `clarification` |
| `system2_attempted` | System 2 was selected by mode/confidence rules |
| `system2_request_attempted` | SDK request method was invoked; not proof of provider receipt |
| `system2_cache_hit` | Validated response reused without a new request |
| `system2.tokens` | Input/output usage for this request, or null when missing; cache hits have `[0, 0]` |
| `system2.groq_ms` | Provider-reported duration when available; null for absent timing or cache hits |
| `system2_failure_usage` | Usage/timing retained for a rejected response; unknown values stay null |
| `latency_ms` | In-process assessment wall time, including requested-provider failures |

A fallback's `path=system1` does not imply that Groq was never attempted or that
no cost was incurred. The evaluator counts attempts separately and refuses a
complete token-cost estimate when any attempt is missing usage.

## Verification and limitations

Offline tests exercise validation, policy floors, malformed model output, cache
identity, rendering, accounting, and package-resource contracts. CI additionally
builds a wheel and checks the installed CLI outside the checkout. CI targets
Python 3.10 and 3.13 and runs a five-repeat fast calibration gate. The gate scores
every repeat; one good first response cannot hide later regressions.
Unexpected clarification fails a calibration case without crashing the scorer.
Repeatability includes status, questions, freeze state, settings, and conflicts,
as well as score, level, route, and comments.

The [fast report](evidence/evals-fast.md) preserves the local code-overhaul run
and its UTC window, before incident enrichment. Its latency excludes CLI startup
and is not an operational guarantee or a benchmark of the enlarged incident set.
The 20-case dataset informed the weights; adding incident context does not add
labeled evaluation cases. Unseen-change quality remains unmeasured.
Live Groq tests require explicit opt-in and credentials, and live provider
quality, latency, cost, and repeatability remain unverified by the offline suite.
No Caveman project telemetry was available for this review; repository metrics
must not be relabeled as Caveman cost or savings evidence.
The [current policy report](evidence/evals-policy-fast.md) records the updated
review routes, settings, and freeze-verification behavior on the calibration set.

No hosted service, multiuser IAM, ingress/egress control plane, live catalog or
freeze synchronization, or postmortem ingestion is implemented. Cross-process
or multiuser reproducibility needs common policy/data versions and an operational
design; the process-local cache does not provide it. See the [FAQ](faq.md).
