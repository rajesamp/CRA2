# CRA2 — ChangeRiskAdvisor 2

CRA2 is a local chat app for change-risk review. You describe a proposed change
in plain English. It answers with:

- A **risk indication** — `low`, `medium`, or `high`, always labeled
  uncalibrated
- **Review questions** for the human who decides
- **The passages it based that on** — incident records, postmortems, and
  runbooks, each with an ID you can open

**CRA2 never approves, rejects, blocks, merges, or deploys a change.** It ranks
review attention and hands the decision to a human. Any model-produced comment
is discarded unless it cites a passage the app actually retrieved. A reported
freeze stays **unconfirmed** until verified; it triggers a verification
question, not a risk weight.

Start with the [two-page overview](docs/architecture-overview.md).

The checkout catalog, 16 original incidents, and 20 evaluation cases are
synthetic. An additional 30 sanitized incident samples
([`data/sample_incidents.json`](data/sample_incidents.json)) were provided by
the user for public distribution and Groq context. Calibration scores measure
calibration, not production accuracy. See the
[code review](docs/evidence/code-review.md) for scope and findings.

## Run it

CRA2 is a local chat app. You need Python 3.13 and
[uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/rajesamp/CRA2.git
cd CRA2

# Install, build the local search index, and download the embedding model once
uv sync --locked --project week1 --python 3.13
uv run --project week1 python -m week1.setup_index --download-model

# Start the app
CRA2_ENV_FILE=.env uv run --project week1 python -m week1.app
```

Open [CRA2 locally](http://127.0.0.1:7860). Pick **Local evidence only** to run
without a Groq key, or **Groq assessment** for a model-chosen risk indication.

For Groq, export `GROQ_API_KEY`, or select a dotenv file explicitly with
`CRA2_ENV_FILE`. CRA2 does not load an arbitrary `.env` from the current
directory.

Full setup, credential boundaries, and optional authenticated sharing are in
[week1/README.md](week1/README.md).

```sh
cp .env.example .env  # add the key locally; never commit .env
CRA2_ENV_FILE=.env uv run --project week1 python -m week1.app
```

**Groq assessment** sends your question, the retrieved passages, and configured
policy facts to Groq. **Local evidence only** makes no network request at all.

## What you can ask

| You ask | You get |
|---|---|
| "How risky is changing checkout-service timeout to 400 ms?" | A risk indication labeled *uncalibrated*, plus review questions (Groq mode). Passages only, no risk claim (local mode) |
| "Have checkout-service retry config changes caused incidents before?" | The matching past incidents, labeled historical |
| "How many incidents do you have?" / "List scenario titles for payment" | Counts and titles from the canonical records |
| "What are the incident fields?" | The four field names |
| "Just approve this change for me." | A refusal and an offer to assess it instead |
| "Is this a freeze window right now?" | "Cannot confirm current state — treat as unconfirmed" |
| Anything off-topic | One sentence and a link. No retrieval, no model |

Questions are capped at 4,000 characters and must name one exact catalog
service from the [checkout catalog](data/checkout_system.json). Name the service
and describe the concrete change; the app asks for detail instead of guessing
when either is missing.

Retrieval matches your question against 46 incident records plus a corpus of
postmortems and runbooks, and keeps the closest three passages. In Groq mode,
any model comment that does not cite a retrieved passage is discarded before
you see it.

## Team settings and freeze verification

The bundled [team settings](data/team_settings.json) mark `auth-service` as
`high_risk`, which holds its risk at medium or above. Set
`CRA2_TEAM_SETTINGS_FILE` to use another validated JSON policy file; it replaces
the bundled file. Your typed question can never override team policy.

When configured settings report an active freeze, the app says the freeze is
**unconfirmed** and asks you to verify it. Otherwise it says `not_reported`,
which is not proof that no freeze exists. CRA2 has no live freeze calendar.

## Evidence integrity

Every comment cites a passage the app actually retrieved, drawn from a checked
allow-list. A citation that is not on that list is discarded before display.
This verifies that a cited passage exists, not that the prose interprets it
correctly.

Your question and the retrieved passages are untrusted input. The prompt design
and local output checks reduce prompt-injection risk; they do not eliminate it.
Never paste credentials into the chat.

Retrieval searches 46 incident records plus the postmortem and runbook corpus.
Same-service history ranks first. Cross-service candidates need at least two
meaningful shared terms; a shared change type alone does not qualify. An
analogous incident is never evidence that the catalog service itself failed
before, and the 28 external service labels in the samples do not create catalog
services. See the [data guide](data/README.md).

## Repeatability

**Local evidence only** is deterministic: the same question returns the same
passages every run.

**Groq assessment** is best effort. Temperature zero, a fixed seed, a selected
model, and a strict JSON schema reduce variation but do not guarantee identical
wording. A bounded in-process cache reuses a recent answer, so a repeated
question may skip the provider entirely. Automatic retries are off, so an
uncached request makes at most one attempt.

Live Groq quality, latency, usage, and cost remain unverified. Historical
evaluation reports keep their original UTC windows and policy baselines; new
runs record current policy rather than overwriting them.

## Evaluate and test

The evaluation runner is repository tooling, not part of the app. It scores the
20 calibration cases in [`evals/`](evals/).

```sh
# Offline: every repeat must score 10/10 and give the same answer
uv run python scripts/run_evals.py --mode fast --repeat 5 --require-repeatable \
  --out /tmp/cra2-policy-fast.md

# Offline app tests
uv run pytest -q -m "not live"
uv run --project week1 python -m pytest week1/tests -q

# Optional live tests; needs a key and may incur charges
CRA2_RUN_LIVE_TESTS=1 uv run pytest -q -m live
```

Live tests need both `CRA2_RUN_LIVE_TESTS=1` and `GROQ_API_KEY`. If the key is
in `.env`, also set `CRA2_ENV_FILE=.env`.

Reports include per-repeat scores, observed levels, repeatability, timings,
provider counts, and usage completeness. A report is written even when the gate
fails. Exit codes: `0` pass, `1` gate failure, `2` invalid options. The default
gate requires 10/10 on every assessment, an assessed outcome per calibration
case, and no unavailable requested model result. Token-cost estimates need both
prices and complete usage; a partial estimate stays labeled partial. Estimates
are not invoices. See [eval methodology](evals/README.md).

## Configuration

Read environment variables before starting the process. Exported values
override an explicitly selected dotenv file.

| Variable | Default | Meaning |
|---|---|---|
| `CRA2_ENV_FILE` | unset | Path to a readable UTF-8 dotenv file |
| `CRA2_TEAM_SETTINGS_FILE` | bundled `data/team_settings.json` | Replacement policy file |
| `GROQ_API_KEY` | unset | Provider credential; never put it in a change file |
| `CRA2_MODEL` | `openai/gpt-oss-20b` | Model ID; changes require recorded evaluation |
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
| `week1/` | The chat app: UI, retrieval, embeddings, routing, response catalog |
| `cra2/` | Shared engine: validation, rule scoring, Groq integration, rules, prompts |
| `data/` | Synthetic catalog, original incidents, sanitized user samples |
| `evals/` | Calibration cases and rubric methodology |
| `scripts/run_evals.py` | Evaluation runner and quality gate |
| `tests/` | Engine regression and opt-in live checks |
| `docs/` | [Product-owner overview](docs/architecture-overview.md), architecture, ADRs, review and evaluation evidence |

Not implemented: hosted service, multiuser auth, live configuration freshness,
and postmortem ingestion. See the [FAQ](docs/faq.md).

## Project records

The [requirements](requirements.md) and [tasks](tasks.md) map the upstream
ChangeRiskAdvisor plan to CRA2, with human acceptance tracked separately from
implementation. Supporting records: [team](docs/team.md),
[six-pager](docs/6-pager.md), [PR/FAQ](docs/pr-faq.md), and
[alignment evidence](docs/evidence/week1-alignment.md).

## Remaining work

Next evidence needs: an authorized live Groq evaluation, an unseen labeled
change set, and a selected Caveman project with provider-complete trace and
ledger data. Local synthetic benchmarks cannot support cross-project cost or
model-speed claims.

CRA2 is separate from [CRA](https://github.com/rajesamp/CRA). Its data and
tests do not establish performance comparisons with that project.
