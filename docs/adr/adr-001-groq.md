# ADR-001: Groq for optional model review

- **Status:** Accepted integration. Model selection stays provisional pending
  live evaluation.
- **Decision date:** 2026-09-27
- **Review date:** 2026-09-28
- **Decision-maker:** Raj Sam, DevOps engineer

## Decision

CRA2 needs local rule-based assessments with optional model review. Routing
stays advisory and model authority stays bounded. Groq is the only implemented
provider.

Mode behavior: `auto` calls System 2 when the rule score is uncertain, `deep`
calls it for every assessable change, and `fast` stays local. Missing or
ambiguous required intent returns clarification questions with no provider call
in any mode.

Model ID: `openai/gpt-oss-20b`. Requests use temperature zero, an integer seed
(default 7), a strict JSON schema, low reasoning effort, and a bounded
completion-token budget. Local response validation complements provider schema
constraints. A process-local cache can avoid a request. An uncached selection
makes at most one SDK attempt, with automatic retries disabled.

The final level never falls below the rule-based level or the policy floors. A
failed response keeps the local answer and adds an availability note. Cache
hits, unavailable clients, rejected responses, and successful requests are
accounted for separately.

Routes describe review attention — `routine-review`, `focused-review`, or
`priority-review` — and never approve or reject a deployment. Effective
`high_risk` and degraded health impose a medium minimum. Reported freeze state
stays explicitly unconfirmed with a verification question and adds no freeze
weight or high floor. Team settings override conflicting request settings, and
the conflict stays visible.

The model may receive selected sanitized samples alongside synthetic history.
Cross-service records need meaningful overlap and stay analogies, not evidence
that the changed service previously failed. Their presence does not require a
live API call.

## Basis and tradeoffs

Groq's [structured-output documentation](https://console.groq.com/docs/structured-outputs)
lists strict JSON-schema support for the selected model family. That documents
an API capability, not task quality, semantic grounding, latency, or
repeatability. Check model availability and compatible request parameters
against the provider's [model documentation](https://console.groq.com/docs/models)
when changing the integration.

On 2026-09-28 a live `openai/gpt-oss-20b` request returned HTTP 400:
`uniqueItems is not supported [unsupported_uniqueItems]`, at schema path
`/properties/comments/items/properties/evidence`. This is an observed API
result, not a claim from the documentation's strict-mode table. The rejected
request produced no successful live assessment.

Compatibility fix: omit only `uniqueItems` from the schema sent to Groq, keep
`strict: true`, and keep the full schema for local validation. Duplicate
evidence entries stay invalid locally. The projection must not mutate the
original schema or relax other request constraints.

A single optional request avoids an agent tool loop, and local rules allow
operation without a key. No controlled comparison against other providers or
prior CRA implementations has been performed. Claims that one model is faster,
cheaper, or better for this task require comparable measurements.

The model ID is configuration, not an immutable provider-version pin.
Temperature zero and a seed reduce variation without guaranteeing identical
fresh responses. A strict schema constrains structure, not correctness.
Returned model IDs and fingerprints are recorded when present.

## Evidence status

| Evidence | State |
|---|---|
| Offline behavior and malformed-response regressions | Covered by repository tests; see [code review](../evidence/code-review.md) |
| Earlier rule calibration and repeatability | Historical [fast report](../evidence/evals-fast.md); predates current routes, freeze policy, and team settings |
| Current review-policy calibration | [Policy report](../evidence/evals-policy-fast.md), offline; no live provider evidence |
| Live schema compatibility | HTTP 400 `unsupported_uniqueItems` observed; provider-only projection added; one projected-schema live assessment succeeded; full live evaluation pending |
| Live rubric quality and fresh-response repeatability | Not measured |
| Live latency and complete token usage | Not measured |
| List-price cost with complete usage and verified prices | Not measured |
| Caveman trace attribution, ledger savings, inferred daily headroom | No selected project evidence available |

No calibration run establishes unseen-change accuracy or provider performance.

A future authorized live evaluation should use the same sample and settings for
each candidate, plus an unseen test set. Record exact UTC windows, returned
model IDs and fingerprints, failures, request counts, usage completeness,
prices with source and date, and evidence paths. Do not treat cache reuse as
model repeatability.

```sh
# These commands send context to Groq and require an exported key.
# Replace INPUT_RATE and OUTPUT_RATE with verified USD per million token prices.
uv run python scripts/run_evals.py --mode deep --repeat 5 --min-score 9 \
  --price-in INPUT_RATE --price-out OUTPUT_RATE
CRA2_RUN_LIVE_TESTS=1 uv run pytest -q -m live
```

## Proposed acceptance criteria

These criteria are targets, not measured achievements:

- At least 9/10 on every assessment.
- No unavailable requested responses.
- Identical status, score, level, route, comments, questions, freeze state,
  settings, and conflicts across five fresh responses for at least 19 of 20
  calibration cases.
- Assessment p95 below 2 seconds in a documented environment.

The runner enforces the score and availability gates. Evaluate the 19/20
consistency and latency criteria from the report. Add `--require-repeatable`
for a stricter 20/20 gate.

Estimate per-1,000 token costs only when both prices and every attempted
request's usage are known. Report known-usage subtotals as partial when needed.
Keep provider-complete cost, inferred headroom, ledger savings, and evidence
cost separate. Local estimates are not Caveman reports or provider invoices.

## Consequences

- Local rules stay usable without provider access, and errors preserve a
  conservative policy floor.
- Model context leaves the machine. Real change data needs a deliberate
  data-sharing decision and suitable current provider terms.
- Model comments still need human review despite schema and citation checks.
- Local credential and payload defenses establish neither hosted isolation nor
  guarantees about external loggers, callers, or provider retention. Hosted
  IAM, ingress/egress, live state freshness, postmortem integration, and
  cross-user reproducibility remain unimplemented.
- Live evidence is required before confirming the model choice. Another Groq
  model can be evaluated through `CRA2_MODEL`; changing providers needs an
  integration change and a new decision record.