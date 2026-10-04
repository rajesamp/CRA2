# CRA2 — ChangeRiskAdvisor 2

CRA2 assesses the risk of a proposed software change and returns:

- A risk level (`low`, `medium`, or `high`)
- A review route (`routine-review`, `focused-review`, or `priority-review`)
- Three comments with evidence references

Local rules score every change. Optional Groq analysis can add concerns when
rules are uncertain or `deep` mode is selected.

**CRA2 never approves, rejects, blocks, merges, or deploys a change.** Routes
rank review attention only. A model response cannot lower the rule-based risk
level. Degraded-service, high-risk team settings, and uncertainty floors also
raise the floor. A reported freeze stays **unconfirmed** until verified; it
triggers a verification question, not a risk weight.

The checkout catalog, 16 original incidents, and 20 evaluation cases are
synthetic. An additional 30 sanitized incident samples
([`data/sample_incidents.json`](data/sample_incidents.json)) were provided by
the user for public distribution and Groq context. Calibration scores measure
calibration, not production accuracy. See the
[code review](docs/evidence/code-review.md) for scope and findings.

## Run it

You need Python 3.10+. The repository pins Python 3.13 for
[uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/rajesamp/CRA2.git
cd CRA2
uv sync --locked

# Assess a bundled sample case
uv run cra2 CHG-02 --mode fast

# Assess a JSON file; --json prints the full result
uv run cra2 my-change.json --mode fast --json

# Assess stdin input
uv run cra2 - --mode fast < my-change.json

# Run offline tests
uv run pytest -q -m "not live"
```

`CHG-01` through `CHG-20` select bundled sample cases. Wheel installs bundle
sample cases, catalog, incidents, rules, and prompts, so the CLI works outside
a source checkout.

For Groq, export `GROQ_API_KEY`, or select a dotenv file explicitly. CRA2 does
not load an arbitrary `.env` from the current directory.

```sh
cp .env.example .env  # add the key locally; never commit .env
CRA2_ENV_FILE=.env uv run cra2 CHG-16 --mode auto
```

`auto` and `deep` send change details, catalog context, and up to five related
incidents to Groq, including the sanitized samples. `fast` is fully local.

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

Required fields: `service` (in the [catalog](data/checkout_system.json)),
`change_type` (in [`rules.json`](cra2/rules.json)), and a concrete `summary`.
Missing or unknown service/type, or a missing/generic summary, returns
`status: "needs_clarification"` with targeted questions. Score, level, and route
are null and no model is called.

Field rules:

- `id` is optional.
- Plan fields are optional strings. Omitted, `null`, empty, or
  whitespace-only values count as missing.
- Strings are trimmed and capped at 10,000 characters.
- Wrong types and unknown fields are rejected.
- Control characters are rejected, except tabs and line breaks.
- `settings` accepts only the booleans `freeze_window_active` and
  `high_risk`. Team policy may override them.
- Input files and stdin are capped at 1,048,576 decoded characters. Duplicate
  JSON keys and excessive nesting are rejected.

CRA2 does not parse free-text requests. The summary heuristic catches common
vague requests; it cannot catch every contradiction.

| Mode | Behavior | Groq key |
|---|---|---|
| `fast` | Local rules only | Not needed |
| `auto` (default) | Calls System 2 only when uncertain | Only for selected requests |
| `deep` | Calls System 2 for every assessable change | Needed unless cached in-process |

Missing credentials, provider errors, and malformed replies fall back to local
rules with an availability note. A model result cannot lower a medium or high
rule-based rating.

## Team settings and freeze verification

The bundled [team settings](data/team_settings.json) mark `auth-service` as
`high_risk`, which forces at least medium risk. Set `CRA2_TEAM_SETTINGS_FILE`
to use another validated JSON policy file; it replaces the bundled file.

Precedence: catalog defaults → request `settings` → team settings. Team
values win even when `false`. Conflicts appear in `settings_conflicts` with
the effective value and its source.

When effective settings report an active freeze, the result reports
`freeze.status = "unconfirmed"` and asks a verification question. Otherwise it
reports `not_reported`, which is not proof that no freeze exists. The freeze
question can accompany a `status: "assessed"` result. CRA2 has no live freeze
calendar.

## Results and evidence

An assessed result contains:

| Field | Content |
|---|---|
| `level`, `score`, `route` | Final risk level, blended 0–1 score, review route |
| `comments` | Exactly three evidence-linked comments |
| `questions` | Freeze-verification or context questions |
| `advisory` | Fixed advisory sentence |
| `system1_score`, `system1_level`, `risk_floor` | Rule scoring and floor provenance |
| `settings`, `settings_conflicts` | Effective settings and visible conflicts |
| `incident_context` | Selected incidents with source dataset, match kind, and matched terms |
| `system2` | Provider telemetry: model, fingerprint, tokens, latency, cache state |

The final level can exceed the blended score's band because the risk floor is
enforced.

Evidence references bind comments to change fields, catalog fields, dependency
edges, or supplied incidents, all from a checked allow-list. This verifies
citation membership, not that the prose interprets the cited fact correctly.
Input text is untrusted; prompt design and local checks reduce, but do not
eliminate, prompt-injection risk.

Incident retrieval searches 46 records and keeps at most five. Same-service
history ranks first, and matching normalized types are preferred. Cross-service
candidates need at least two meaningful shared terms; a shared change type
alone does not qualify. `Deployment` is compared as `Code deploy`; stored
labels stay unchanged. An analogous incident is never evidence that the catalog
service itself failed before. The 28 external service labels in the samples do
not create catalog services. See the [data guide](data/README.md).

## Repeatability and performance

System 1 is deterministic for fixed input, rules, and catalog data. System 2:
temperature zero, a fixed seed, a selected model ID, and a strict JSON schema
improve consistency but do not guarantee identical fresh answers. The backend
fingerprint is recorded when available.

System 2 keeps a bounded in-process cache. A cache hit avoids a new SDK request;
it does not measure fresh-response repeatability. Evaluations clear the cache
between non-fast assessments. Automatic SDK retries are off, so an uncached
assessment makes at most one SDK attempt. Attempt telemetry is not proof the
provider received or billed a request.

Historical reports keep their UTC windows and policy baselines:

- [Enriched fast report](docs/evidence/evals-enriched-fast.md)
- [Original fast report](docs/evidence/evals-fast.md)

Both predate the review-only routes and freeze policy. New runs must record
current policy and data; never overwrite historical results. The
[current policy report](docs/evidence/evals-policy-fast.md) records
review-only routes, freeze questions, and settings behavior across repeats,
with corpus/rules/catalog/settings hashes. Timings exclude CLI startup and are
not service-level guarantees. Live Groq quality, latency, usage, and costs
remain unverified.

## Evaluate and test

```sh
# Offline: every repeat must score 10/10 and give the same answer
uv run python scripts/run_evals.py --mode fast --repeat 5 --require-repeatable \
  --out /tmp/cra2-policy-fast.md

# Optional live tests; needs a key and may incur charges
CRA2_RUN_LIVE_TESTS=1 uv run pytest -q -m live

# Optional live evaluation; replace price placeholders with verified USD/1M rates
uv run python scripts/run_evals.py --mode deep --repeat 5 --min-score 9 \
  --require-repeatable --price-in INPUT_RATE --price-out OUTPUT_RATE
```

Live tests need both `CRA2_RUN_LIVE_TESTS=1` and `GROQ_API_KEY`. If the key is
in `.env`, also set `CRA2_ENV_FILE=.env`. The runner defaults to `fast` even
though the CLI defaults to `auto`.

Reports include per-repeat scores, observed levels, repeatability, timings,
provider counts, and usage completeness. A report is written even when the gate
fails. Exit codes: `0` pass, `1` gate failure, `2` invalid options. The default
gate requires 10/10 on every assessment, an assessed outcome per calibration
case, and no unavailable requested System 2 result. `--min-score` sets the
per-assessment threshold. `--require-repeatable` needs at least two repeats and
compares status, score, level, route, comments, questions, freeze state,
settings, and conflicts.

Both token prices are required for a cost estimate. Missing usage keeps the
full estimate unknown; a known-usage subtotal stays explicitly partial.
Estimates are not invoices or measured costs. See
[eval methodology](evals/README.md).

## Configuration

Read environment variables before starting the process. Exported values
override an explicitly selected dotenv file.

| Variable | Default | Meaning |
|---|---|---|
| `CRA2_ENV_FILE` | unset | Path to a readable UTF-8 dotenv file |
| `CRA2_TEAM_SETTINGS_FILE` | bundled `data/team_settings.json` | Replacement policy file |
| `GROQ_API_KEY` | unset | Provider credential; never put it in a change file |
| `CRA2_MODEL` | `openai/gpt-oss-20b` | Model ID; changes require recorded evaluation |
| `CRA2_MODE` | `auto` | `fast`, `auto`, or `deep`; CLI `--mode` overrides it |
| `CRA2_SEED` | `7` | Integer sampling seed; repeatability is best effort |
| `CRA2_TIMEOUT_S` | `10` | Positive finite SDK timeout; no automatic retries |
| `CRA2_MAX_TOKENS` | `1024` | Positive completion-token cap |
| `CRA2_RUN_LIVE_TESTS` | unset | Set to `1` to enable tests that call Groq |

Risk thresholds, weights, and comment templates live in `cra2/rules.json`.
Changing catalog state, rules, or prompts changes assessment policy and
requires updated evidence.

## Repository layout

| Path | Purpose |
|---|---|
| `cra2/` | Validation, rule scoring, Groq integration, routing, CLI, rules, prompts |
| `data/` | Synthetic catalog, original incidents, sanitized user samples |
| `evals/` | Calibration cases and rubric methodology |
| `scripts/run_evals.py` | Evaluation runner and quality gate |
| `tests/` | Offline regression, packaging, and opt-in live checks |
| `docs/` | [Product-owner overview](docs/architecture-overview.md), architecture, ADRs, review and evaluation evidence |

Hosted service, multiuser auth, ingress/egress controls, live configuration
freshness, and postmortem integrations are not implemented. See the
[FAQ](docs/faq.md).

## Week 1 alignment and Gradio UI

The additive [requirements](requirements.md) and [tasks](tasks.md) map upstream
ChangeRiskAdvisor Week 1 tasks 1–11 to CRA2, with human acceptance tracked
separately. Core CLI and earlier sections are preserved. See the
[team record](docs/team.md), [six-pager](docs/6-pager.md),
[PR/FAQ](docs/pr-faq.md), and [alignment evidence](docs/evidence/week1-alignment.md).

From the repository root, launch the optional UI in its own environment:

```sh
uv sync --locked --project week1 --python 3.13
uv run --project week1 python -m week1.setup_index --download-model
CRA2_ENV_FILE=.env uv run --project week1 python -m week1.app
```

Open [CRA2 locally](http://127.0.0.1:7860). The explicit setup step downloads a
checksum-pinned local embedding model; runtime retrieval stays local. Omit
`CRA2_ENV_FILE=.env` and choose **Local evidence only** to run without Groq.
Setup details, credential boundaries, and optional authenticated sharing are in
[week1/README.md](week1/README.md). Operational tools and persistent
conversational memory remain Week 2 work.

## Remaining work

Next evidence needs: an authorized live Groq evaluation, an unseen labeled
change set, and a selected Caveman project with provider-complete trace and
ledger data. Local synthetic benchmarks cannot support cross-project cost or
model-speed claims.

CRA2 is separate from [CRA](https://github.com/rajesamp/CRA). Its data and
tests do not establish performance comparisons with that project.
