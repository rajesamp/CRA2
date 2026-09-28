# ADR-001: Groq for optional System 2 review

- **Status:** Accepted integration; model selection remains provisional pending live evaluation.
- **Original decision date:** 2026-09-27
- **Review date:** 2026-09-28
- **Decision-maker:** Raj Sam, DevOps engineer

## Context and decision

CRA2 needs local rule-based assessments with optional model review, while keeping
routing advisory and bounding model authority. The implemented integration uses
Groq exclusively. `auto` selects System 2 when the rule score is uncertain;
`deep` selects it for every assessable change; `fast` remains entirely local.
Missing/ambiguous required intent returns clarification questions without a
provider call in every mode.

The selected model ID is `openai/gpt-oss-20b`. Requests use temperature zero, an
integer seed (default 7), strict JSON schema, low reasoning effort, and a bounded
completion-token budget. Local response validation complements provider schema
constraints. A process-local cache can avoid a request. An uncached selection
makes at most one SDK request attempt, with automatic retries disabled.

The final level cannot fall below the rule-based level and policy floors.
Failure to obtain a valid response retains the local answer and an availability
note. A cache hit, unavailable client, rejected response, and successful request
are accounted for separately.
Routes describe review attention (`routine-review`, `focused-review`, or
`priority-review`); they never approve or reject a deployment. Effective
`high_risk` and degraded-health signals impose a medium minimum. Reported freeze
state remains explicitly unconfirmed with a verification question, without
adding freeze risk weight or a high floor. Team settings override conflicting
request settings, and the conflict remains visible.

The model may receive selected sanitized user incident samples alongside the
synthetic history. Cross-service records require meaningful overlap and remain
analogies, not evidence that the changed service previously failed. Their
presence does not make a live API call part of this code change.

## Basis and tradeoffs

Groq's [structured-output documentation](https://console.groq.com/docs/structured-outputs)
lists strict JSON-schema support for the selected model family. This establishes
an API capability, not task-specific quality, semantic grounding, latency, or
repeatability. Confirm model availability and compatible request parameters
against the provider's [model documentation](https://console.groq.com/docs/models)
when changing the integration.

A single optional request avoids an agent tool loop within CRA2, and local rules
allow operation without a key. No controlled comparison with other providers or
prior CRA implementations has been performed in this review. Claims that one
model is faster, cheaper, or better for this task require comparable measurements.

The model ID is a configuration choice, not an immutable provider-version pin.
Temperature zero and seed reduce sources of variation but do not guarantee
identical fresh responses. Strict schema constrains structure, not correctness.
Returned model IDs and fingerprints are recorded when present.

## Evidence and acceptance criteria

The [fast report](../evidence/evals-fast.md) records rule calibration on 20
synthetic cases and includes every repeat. Its weights were tuned using those
cases. That report predates the current routes, freeze-verification policy, and
team settings; it is retained as historical evidence. A new policy run must be
recorded separately. No calibration run establishes unseen-change accuracy or
provider performance.

| Evidence | State after this review |
|---|---|
| Offline behavior and malformed-response regressions | Covered by repository tests; see [review report](../evidence/code-review.md) |
| Earlier rule calibration and repeatability | Historical fast report; evaluate current policy separately |
| Current review-policy calibration | [Policy report](../evidence/evals-policy-fast.md), offline; no live provider evidence |
| Live Groq rubric quality and fresh-response repeatability | Not measured |
| Live Groq latency and complete token usage | Not measured |
| Provider list-price cost using complete usage and verified prices | Not measured |
| Caveman trace attribution, verified ledger savings, and inferred daily headroom | No selected project evidence available |

A future authorized live evaluation should use the same sample and settings for
each candidate, plus an unseen test set. Record exact UTC windows, returned model
IDs/fingerprints, failures, request counts, usage completeness, prices and their
source/date, and evidence paths. Do not treat cache reuse as model repeatability.

```sh
# These commands send context to Groq and require an exported key.
# Replace INPUT_RATE and OUTPUT_RATE with verified USD per million token prices.
uv run python scripts/run_evals.py --mode deep --repeat 5 --min-score 9 \
  --price-in INPUT_RATE --price-out OUTPUT_RATE
CRA2_RUN_LIVE_TESTS=1 uv run pytest -q -m live
```

The provisional selection target is at least 9/10 **on every assessment**, no
unavailable requested responses, identical status/score/level/review route,
comments, questions, freeze state, settings, and conflicts across five
fresh responses for at least 19 of 20 calibration cases, and assessment p95
below 2 seconds in a documented environment. These are proposed acceptance
criteria, not measured achievements. The runner checks the score and availability
gates; evaluate the 19/20 and latency criteria from the report. Add
`--require-repeatable` to enforce a stricter 20/20 consistency gate.

Only estimate per-1,000 token costs when both prices and every attempted
request's usage are known. Report known-usage subtotals as partial when needed.
Keep measured provider-complete cost, inferred daily headroom, verified ledger
savings, and the cost of collecting evidence separate. Local estimates are not
Caveman reports or provider invoices.

## Consequences

- Local rules remain usable without provider access; errors preserve a
  conservative policy floor.
- Model context leaves the machine. Real change data requires a deliberate
  data-sharing decision and suitable current provider terms.
- Model comments still require human review despite schema and citation checks.
- Local credential/payload defenses do not establish hosted isolation or a
  guarantee about every external logger, caller, or provider retention system.
  Hosted IAM, ingress/egress, live state freshness, postmortem integration, and
  cross-user reproducibility remain separate unimplemented operational work.
- Live evidence is required before confirming the model choice. Another Groq
  model can be evaluated through `CRA2_MODEL`; changing providers would require
  an integration change and a new decision record.
