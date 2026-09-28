# CRA2 — ChangeRiskAdvisor 2

CRA2 gives Raj Sam, a DevOps engineer, an advisory assessment of a structured
software change: a risk level, a recommended review route, and three comments
with evidence references. Local rules run for every assessment; optional Groq
analysis can add concerns when the rules are uncertain or `deep` mode is selected.

**CRA2 never approves, blocks, merges, or deploys a change.** `auto-approve`,
`review`, and `escalate-or-block` are route labels for a human to consider.
A model response cannot lower the rule-based risk level. Freeze, degraded-service,
and uncertainty floors also apply.

The included checkout system, incidents, and evaluation cases are synthetic.
Passing these cases is a calibration check, not evidence of production accuracy.
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

`auto` and `deep` may send change details, catalog context, and related synthetic
incidents to Groq. Use `fast` for an entirely local assessment. Review the data
that will be shared before adapting this sample to real changes.

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

`service`, `change_type`, and `summary` are required, nonempty strings.
`service` must appear in [the catalog](data/checkout_system.json); `change_type`
must appear in [the rules](cra2/rules.json). `id` is optional. The three plan
fields are optional strings; omitted, `null`, empty, or whitespace-only plans
count as missing. Fields are trimmed, limited to 10,000 characters each, and
unknown fields are rejected. CRA2 does not parse free-text requests.
Input files and stdin are limited to 1,048,576 decoded Unicode characters.
Duplicate JSON keys and excessive nesting are rejected. Invisible/control
characters are rejected in fields except ordinary tabs and line breaks, so
invisible plan text cannot bypass a missing-plan rule.

| Mode | Behavior | Groq key |
|---|---|---|
| `fast` | Local rules only | Not needed |
| `auto` (CLI default) | Rules; request System 2 only when uncertain | Needed only for selected requests |
| `deep` | Rules; request System 2 for every assessment | Needed unless the response is already cached in this process |

Missing credentials, provider errors, and malformed replies fall back to local
rules and produce an availability note. Only a confident low rule-based result
can reach the `auto-approve` route. A successful model result still cannot lower
a medium or high rule-based decision.

## Results and evidence

Human-readable output contains the risk, score, route, three comments, and an
advisory sentence. JSON also includes `system1_score`, `system1_level`,
`risk_floor`, `uncertain`, `advisory`, and provider telemetry. The final level can
be above the raw blended score's band because the risk floor is enforced.

Evidence references link comments to change fields, catalog fields, dependency
relationships, or supplied incidents. References are checked against allowed
keys. This verifies citation membership; it cannot prove that a model's prose
correctly interprets the cited fact. Input text is untrusted, and the prompt
and local output checks reduce but cannot eliminate prompt-injection risk.

The [architecture](docs/architecture.md) describes scoring, routing, validation,
cache behavior, and failure handling. [ADR-001](docs/adr/adr-001-groq.md) records
the provisional Groq model choice and the evidence still needed.

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

The regenerated [fast evaluation report](docs/evidence/evals-fast.md) contains
local timing measurements and their exact UTC window. These timings exclude
CLI startup and are not service-level guarantees. Live Groq quality, latency,
usage, and costs have not been validated by this overhaul.

## Evaluate and test

```sh
# Offline: every repeat must score 10/10 and give the same answer.
uv run python scripts/run_evals.py --mode fast --repeat 5 --require-repeatable

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
gate requires at least 10/10 on **every** assessment and no unavailable requested
System 2 result. `--min-score` changes the per-assessment threshold;
`--require-repeatable` requires at least two repeats.

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
| `data/` | Canonical synthetic catalog and incident files |
| `evals/` | Canonical calibration cases and rubric methodology |
| `scripts/run_evals.py` | Repository evaluation runner and quality gate |
| `tests/` | Offline regression, package-installation, and opt-in live checks |
| `docs/` | Architecture, ADR, review, and evaluation evidence |

The next evidence needed is an authorized live Groq evaluation, a separate set
of unseen labeled changes, and a selected Caveman project with provider-complete
trace and ledger data. No cross-project cost or model-speed claims can be made
from the local synthetic benchmark.

CRA2 is separate from [CRA](https://github.com/rajesamp/CRA). This repository's
data and tests do not establish performance comparisons with that project.
