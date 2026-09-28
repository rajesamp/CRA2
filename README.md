# CRA2 — ChangeRiskAdvisor 2

CRA2 gives Raj Sam, a DevOps engineer, an advisory assessment of a structured
software change: a risk level, a recommended review route, and three comments
with evidence references. Local rules run for every assessment; optional Groq
analysis can add concerns when the rules are uncertain or `deep` mode is selected.

**CRA2 never approves, rejects, blocks, merges, or deploys a change.** Its routes
describe review attention: low → `routine-review`, medium → `focused-review`,
high → `priority-review`. A model response cannot lower the rule-based risk level.
Degraded-service, high-risk team settings, and uncertainty floors also apply.
A reported freeze is explicitly **unconfirmed** and prompts a verification
question; it does not itself add risk weight or force a high rating.

The checkout catalog, 16 original incidents, and 20 evaluation cases are synthetic.
An additional [30 sanitized incident samples](data/sample_incidents.json) were
provided by the user for public GitHub distribution and Groq assessment context.
Their original service/type labels and provenance are preserved separately from
the synthetic fixtures. Passing the calibration cases is not evidence of
production accuracy or successful retrieval of every sample.
See the [code review](docs/evidence/code-review.md) for the overhaul findings and
verification scope.

## Run locally

The package supports Python 3.10 and later. The repository's `.python-version`
selects Python 3.13 for [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/rajesamp/CRA2.git
cd CRA2
uv sync --locked
uv run cra2 CHG-02 --mode fast
uv run cra2 my-change.json --mode fast --json
uv run cra2 - --mode fast < my-change.json
uv run pytest -q -m "not live"
```

`CHG-01` through `CHG-20` select the bundled sample cases. Normal wheel installs
include the sample cases, catalog, incidents, rules, and prompt assets, so the
CLI can run outside a source checkout. The evaluation report script itself is
repository tooling.

For Groq, export `GROQ_API_KEY` before starting CRA2, or explicitly select a
dotenv file. An arbitrary `.env` in the current directory is not loaded.

```sh
cp .env.example .env  # edit the key locally; never commit .env
CRA2_ENV_FILE=.env uv run cra2 CHG-16 --mode auto
```

`auto` and `deep` may send change details, catalog context, and up to five related
incidents to Groq, including the sanitized user samples. Use `fast` for an entirely
local assessment. Adding the incident samples did not make any live Groq calls.

## Input contract

```json
{
  "id": "MY-CHANGE-01",
  "service": "inventory-service",
  "change_type": "Config change",
  "summary": "Raise the stock-count cache TTL from 30 s to 120 s.",
  "deploy_plan": "",
  "rollback_plan": "Set the TTL back to 30 s.",
  "monitoring_plan": "Nightly reconciliation drift."
}
```

To assess a change, `service` must appear in [the catalog](data/checkout_system.json),
`change_type` in [the rules](cra2/rules.json), and `summary` must describe a
concrete modification. Missing/unknown service or type and missing/generic
summaries return `status: "needs_clarification"` with targeted `questions`.
The level, score, and route are null, and no model is called. A deterministic
summary heuristic catches common vague requests; it cannot identify every vague
or contradictory statement. `id` is optional. The three plan
fields are optional strings; omitted, `null`, empty, or whitespace-only plans
count as missing. String fields are trimmed and limited to 10,000 characters
each. Wrong types and unknown fields are rejected. CRA2 does not parse free-text
requests. Optional `settings` accepts only boolean `freeze_window_active` and
`high_risk` values; team policy may override these request values.
Input files and stdin are limited to 1,048,576 decoded Unicode characters.
Duplicate JSON keys and excessive nesting are rejected. Invisible/control
characters are rejected in fields except ordinary tabs and line breaks, so
invisible plan text cannot bypass a missing-plan rule.

| Mode | Behavior | Groq key |
|---|---|---|
| `fast` | Local rules only | Not needed |
| `auto` (CLI default) | Rules; request System 2 only when uncertain | Needed only for selected requests |
| `deep` | Rules; request System 2 for each assessable change | Needed unless the response is already cached in this process |

Missing credentials, provider errors, and malformed replies fall back to local
rules and produce an availability note. A successful model result cannot lower
a medium or high rule-based rating. All three routes remain review guidance.

## Team settings and freeze verification

The bundled [team settings](data/team_settings.json) mark `auth-service` as
`high_risk`, which requires at least medium risk / focused review. Set
`CRA2_TEAM_SETTINGS_FILE` to use another validated JSON policy file; it replaces
the bundled file. Settings resolve in this order: catalog/default values,
request `settings`, then explicitly configured team values. Team values win even
when they are `false`. Conflicts between request and team settings are visible in
`settings_conflicts`, with the effective value and its source.

The `freeze` result reports `unconfirmed` when effective settings report an
active freeze, otherwise `not_reported`. `not_reported` is not proof that no
freeze exists. A freeze question can accompany `status: "assessed"`; the risk
assessment proceeds using the other evidence. CRA2 has no live freeze calendar.

## Results and evidence

An assessed result contains risk, score, review route, three comments, questions,
and an advisory sentence. JSON also includes `status`, `freeze`, `settings`,
`settings_conflicts`, `system1_score`, `system1_level`, `risk_floor`, `uncertain`,
`advisory`, provider telemetry, and `incident_context`.
The latter contains the selected incident records with their source dataset,
same-service/analogy classification, and matching terms. The final level can
be above the raw blended score's band because the risk floor is enforced.

Evidence references link comments to change fields, catalog fields, dependency
relationships, or supplied incidents. References are checked against allowed
keys. This verifies citation membership; it cannot prove that a model's prose
correctly interprets the cited fact. Input text is untrusted, and the prompt
and local output checks reduce but cannot eliminate prompt-injection risk.

The [architecture](docs/architecture.md) describes scoring, routing, validation,
cache behavior, and failure handling. [ADR-001](docs/adr/adr-001-groq.md) records
the provisional Groq model choice and the evidence still needed.

Incident retrieval searches 46 records and retains at most five. Same-service
history ranks first, with matching normalized types preferred. Cross-service
candidates require at least two meaningful shared terms; a shared change type
alone is insufficient. They rank by informative token overlap, with type and recency
breaking ties. `Deployment` is compared as `Code deploy` while the stored label
remains unchanged. Other-service or no-change incidents can supply an
analogy when they share enough informative terms; an analogous incident never
becomes evidence that the catalog service itself failed before. The 28 external
service labels in the new samples do not create new catalog services. See the
[data guide](data/README.md) for retrieval and provenance details.

## Repeatability and performance

System 1 is deterministic for fixed normalized input, rules, and catalog data;
elapsed time is not deterministic. Temperature zero, a fixed seed, a selected
model ID, and strict JSON schema improve System 2 consistency but do not
establish deterministic model answers. A model ID is not an immutable backend
version. The backend fingerprint is recorded when available.

System 2 has a bounded in-process cache. A cache hit avoids a new SDK request;
it does not demonstrate fresh-response repeatability. Evaluations clear that
cache between non-fast assessments. Automatic SDK retries are disabled, so an
uncached assessment makes at most one SDK request attempt. Attempt telemetry
is not proof that the provider received or billed a request.

The [enriched fast report](docs/evidence/evals-enriched-fast.md) and
[original fast report](docs/evidence/evals-fast.md) preserve earlier policy
baselines and their UTC windows. They predate the review-only routes and freeze
verification policy. New runs must record the current policy and data rather
than overwrite those historical results. Timings exclude CLI startup and are
not service-level guarantees. Live Groq quality, latency, usage, and costs remain
unverified.
The [current policy report](docs/evidence/evals-policy-fast.md) records the
review-only routes, freeze questions, and settings behavior across all repeats,
with hashes of the loaded incident corpus, rules, catalog, and team settings.

## Evaluate and test

```sh
# Offline: every repeat must score 10/10 and give the same answer.
uv run python scripts/run_evals.py --mode fast --repeat 5 --require-repeatable \
  --out /tmp/cra2-policy-fast.md

# Explicit live checks: needs a key and can incur provider charges.
CRA2_RUN_LIVE_TESTS=1 uv run pytest -q -m live

# Explicit live evaluation; replace price placeholders with verified USD/1M rates.
uv run python scripts/run_evals.py --mode deep --repeat 5 --min-score 9 \
  --require-repeatable --price-in INPUT_RATE --price-out OUTPUT_RATE
```

Live tests require both `CRA2_RUN_LIVE_TESTS=1` and `GROQ_API_KEY`. If the key is
in `.env`, also set `CRA2_ENV_FILE=.env` explicitly. The runner defaults to
`fast` even though the assessment CLI defaults to `auto`.

Reports include every repeat's score, observed levels, repeatability, timings,
provider selection/attempt/cache/failure counts, and usage completeness.
A report is written even when the quality gate fails. Exit status is `0` for
pass, `1` for a gate failure, and `2` for invalid command options. The default
gate requires at least 10/10 on **every** assessment, an assessed outcome for each
calibration case, and no unavailable requested System 2 result. `--min-score`
changes the per-assessment threshold; `--require-repeatable` requires at least
two repeats and compares status, score, level, route, comments, questions, freeze
state, effective settings, and surfaced conflicts.

Both token prices are required for a token-cost estimate. Missing provider
usage leaves a complete estimate unknown; a known-usage subtotal remains
explicitly partial. These estimates are not invoices or Caveman measured
costs, verified savings, or inferred headroom. See [eval methodology](evals/README.md).

## Configuration

Settings are captured when `cra2.config` is first imported. Set environment
variables before starting the process. Exported values override values from an
explicitly selected dotenv file.

| Variable | Default | Meaning |
|---|---|---|
| `CRA2_ENV_FILE` | unset | Explicit path to a readable UTF-8 dotenv file |
| `CRA2_TEAM_SETTINGS_FILE` | bundled `data/team_settings.json` | Explicit replacement policy file with team and per-service boolean settings |
| `GROQ_API_KEY` | unset | Provider credential; never include it in a change file |
| `CRA2_MODEL` | `openai/gpt-oss-20b` | Model ID; changes require recorded evaluation |
| `CRA2_MODE` | `auto` | `fast`, `auto`, or `deep`; CLI `--mode` overrides it |
| `CRA2_SEED` | `7` | Integer sampling seed; repeatability is best effort |
| `CRA2_TIMEOUT_S` | `10` | Positive finite SDK request timeout; no automatic retries |
| `CRA2_MAX_TOKENS` | `1024` | Positive completion-token cap |
| `CRA2_RUN_LIVE_TESTS` | unset | Set to `1` to enable tests that call Groq |

Risk thresholds, weights, and comment templates live in `cra2/rules.json`.
Changing catalog state, rules, or prompts changes the assessment policy and
requires updated evidence.

## Repository layout and remaining work

| Path | Purpose |
|---|---|
| `cra2/` | Validation, rule scoring, Groq integration, routing, CLI, rules, prompts |
| `data/` | Synthetic catalog/original incidents and separately sourced sanitized user incident samples |
| `evals/` | Canonical calibration cases and rubric methodology |
| `scripts/run_evals.py` | Repository evaluation runner and quality gate |
| `tests/` | Offline regression, package-installation, and opt-in live checks |
| `docs/` | Architecture, ADR, review, and evaluation evidence |

The [FAQ and deployment boundaries](docs/faq.md) describe clarification, settings,
incident relevance, credential handling, and reproducibility. Hosting, multiuser
authentication/authorization, ingress/egress controls, live configuration
freshness, and postmortem integrations are not implemented.

The next evidence needed is an authorized live Groq evaluation, a separate set
of unseen labeled changes, and a selected Caveman project with provider-complete
trace and ledger data. No cross-project cost or model-speed claims can be made
from the local synthetic benchmark.

CRA2 is separate from [CRA](https://github.com/rajesamp/CRA). This repository's
data and tests do not establish performance comparisons with that project.


## Week 1 alignment and Gradio UI

The additive [requirements](requirements.md) and [tasks](tasks.md) map upstream
ChangeRiskAdvisor Week 1 tasks 1–11 to CRA2, with human acceptance recorded
separately from implementation. Existing sections above and the core CLI are
preserved. See the [team record](docs/team.md), [six-pager](docs/6-pager.md),
[PR/FAQ](docs/pr-faq.md), and [alignment evidence](docs/evidence/week1-alignment.md).

From the repository root, launch the optional UI in its separate environment:

```sh
uv sync --locked --project week1 --python 3.13
uv run --project week1 python -m week1.setup_index --download-model
CRA2_ENV_FILE=.env uv run --project week1 python -m week1.app
```

Open [CRA2 locally](http://127.0.0.1:7860). The explicit setup downloads a
checksum-pinned local embedding model; runtime retrieval is local. Omit
`CRA2_ENV_FILE=.env` and choose **Local evidence only** for use without Groq.
Detailed setup, credential boundaries, and optional authenticated sharing are in
[week1/README.md](week1/README.md). Current operational tools and persistent
conversational memory remain Week 2 work. Team review, a teammate's fresh-clone
run, public sharing, and a team-channel post require their own evidence.
