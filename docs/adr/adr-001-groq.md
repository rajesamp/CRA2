# ADR-001: Groq as the only model provider, one call per unsure change

- **Status:** Accepted. The model pin is provisional until the live eval run.
- **Date:** 2026-09-27
- **Decision-makers:** Raj Sam (DevOps engineer)

## Context

The earlier ChangeRiskAdvisor builds answered through an agent loop. The model
decided which tools to call, so each question took two to four model calls in
sequence, and every call re-sent a growing prompt. One build ran a 7B model
locally through Ollama; the other ran Gemini through Google ADK. Answers were
too slow for a reviewer who checks a dozen changes a day, and nothing pinned
the answer: the same question could come back with a different rating.

The product owner asked for three things:

- answers in milliseconds or seconds,
- the same level and the same three comments for the same change, every time,
- a model provider chosen and justified with evals.

## Decision

- **Provider: Groq only.** System 2 is one Groq chat-completions call.
- **Only when needed.** A rule-based System 1 answers the changes it is sure
  about. Groq is called only when System 1's score is within 0.05 of a
  threshold, or in `deep` mode.
- **Pinned and deterministic.** The model is pinned (`CRA2_MODEL`, default
  `openai/gpt-oss-20b`). Temperature is 0, the seed is fixed at 7, reasoning
  effort is low with reasoning left out of the reply, and output is strict JSON
  schema with enums. The request timeout is 10 s with 1 retry.
- **No agent loop.** Context (catalog, dependency graph, incidents) is looked
  up in code and sent in one compact payload, so the model never chooses
  tools.

## Why Groq

- **Latency.** Groq serves open-weight models on its own inference hardware,
  built for low latency and high tokens-per-second. One call with a small
  payload fits the "seconds, not minutes" target.
- **Determinism controls.** The Groq API takes `seed` and `temperature`, and
  returns `system_fingerprint` so backend changes can be spotted. The Python
  SDK (1.7.0) documents seeded sampling as best effort, so CRA2 also caches,
  keeps System 1 in charge of most decisions, and tests determinism live.
- **Structured output.** `response_format` with `json_schema` and
  `strict: true` constrains the reply to the schema. That makes ratings and
  comment areas enums instead of free text.
- **Local development.** There is nothing to host: a key in `.env` is enough.
  `fast` mode runs with no key at all.

## Alternatives considered

| Option | Pros | Cons |
|---|---|---|
| Local Ollama model (the LocalCRA build) | No key, and data stays on the machine | A 7B model on a laptop is slow, and weaker at careful reasoning; the agent loop multiplies the cost |
| Gemini through Google ADK (the CRA build) | Capable model, and ADK tooling | The agent loop makes several calls per question; not the "Groq only" requirement |
| Groq `openai/gpt-oss-120b` | Larger model, likely better comments | Slower and dearer than 20b. A candidate if the eval shows 20b's comments are weak. |
| Groq non-reasoning models, such as `llama-3.3-70b-versatile` | No reasoning tokens | Strict schema mode is not available for every model; CRA2 needs it |
| **Groq `openai/gpt-oss-20b`, one call, System 1 gate (chosen)** | Fast, strict schema, seed, low reasoning effort | Needs a key and network; seeded determinism is best effort |

The model IDs and strict-schema support above come from the Groq Python SDK
1.7.0. This container could not reach Groq's documentation or API to confirm
current model availability and prices. Check both at
[console.groq.com/docs/models](https://console.groq.com/docs/models) before the
eval run.

## Evaluation (to fill in)

Run on a machine that can reach `api.groq.com`, with the prices from Groq's
pricing page:

```sh
uv run python scripts/run_evals.py --mode deep --repeat 5 --price-in <in> --price-out <out>
CRA2_MODEL=openai/gpt-oss-120b uv run python scripts/run_evals.py --mode deep --repeat 5 --price-in <in> --price-out <out>
uv run pytest -q tests/test_live_groq.py
```

| Model | Mean rubric score /10 | Level correct /20 | Same answer 5x /20 | p50 / p95 latency (ms) | Cost per 1,000 assessments (USD) |
|---|---|---|---|---|---|
| `openai/gpt-oss-20b` | pending | pending | pending | pending | pending |
| `openai/gpt-oss-120b` | pending | pending | pending | pending | pending |
| System 1 only (`fast`, no Groq) | 10.00 | 20 | 20 | 0.047 / 0.082 | 0 |

The System 1 row is calibration, not evidence: its weights were set with these
cases in view.

**Decision rule.** Keep `openai/gpt-oss-20b` if it scores at least 9/10, gives
the same answer five times on at least 19 of 20 cases, and stays under 2 s at
p95. Otherwise, try `openai/gpt-oss-120b` against the same bar. Record the
result in this ADR.

## Consequences

- **Positive:** Most changes are answered offline in microseconds. The rest
  take one network round trip. Answers are repeatable and grounded, and the
  provider choice is testable.
- **Negative:** System 2 needs a key and network access, and change details
  are sent to Groq. The data here is synthetic; check Groq's data-retention
  terms before sending real change data. Seeded sampling is best effort.
- **Reversible:** Yes. The provider is confined to `cra2/system2.py` and
  `config.py`.
