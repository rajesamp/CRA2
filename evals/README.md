# Evaluation cases and methodology

`cases.json` contains 20 synthetic changes to the checkout system in `data/`.
These cases informed the rule weights, so they are calibration fixtures. They
are not a held-out test set or evidence of production accuracy.

Incident context now includes the original 16 synthetic records and 30 separately
stored, sanitized user-provided samples. These 46 incident records are context,
not 46 evaluation cases. The 20 calibration inputs remain assessable. Expected
routes now express review attention: `routine-review`, `focused-review`, and
`priority-review`. Removing the unconfirmed-freeze weight/high floor deliberately
changes CHG-04 to medium and CHG-08 to low; their freeze questions and incident
citations remain required. These are policy changes, not adjustments to conceal
a failing test. Additional incident data alone never justifies changing answers.

Each case includes the structured `change`, `expected` level and route, desired
comment tags (`flags`), acceptable incident citations (`cite_any`), and a
10-point `rubric`.

| Check | Points | Full marks |
|---|---|---|
| level | 4 | Exact expected level; one level too high earns 1 point, any other mismatch earns 0 |
| route | 2 | Exact expected advisory route |
| flags | 2 | Expected tags covered, with proportional credit for partial coverage |
| cite | 1 | Every comment cites supplied evidence and, when specified, at least one `cite_any` incident is cited |
| format | 1 | Three distinct comment tags, no checked approval phrasing, rendered advisory sentence |

Citation checking verifies allowed-key membership. The rubric does not establish
whether arbitrary model prose is true or whether every unsafe phrase is caught.
Local output validation and policy regression tests provide separate checks.

## Coverage and limits

The cases cover eight services, seven change types, and expected levels of six
low, nine medium, and five high. Examples include unconfirmed freezes (CHG-04,
CHG-08), degraded direct dependencies (CHG-10, CHG-16), missing rollback plans
(CHG-01, CHG-12, CHG-13, CHG-20), config drift (CHG-01, CHG-11), and deploy-order
risk (CHG-05, CHG-13, CHG-19). They do not cover live operational freshness or
unseen production systems. Add independently labeled, unseen changes before
making generalization claims.

The added samples retain 28 external service labels. Retrieval can select
cross-service analogies with at least two meaningful shared terms; change type
alone does not qualify a candidate. These
matches must not trigger the same-service repeat-incident penalty. Regression
coverage for selection order, bounded context, provenance, and this distinction
is separate from the 20-case calibration score. Neither a passing score nor the
presence of a sample proves that its most relevant incident will be retrieved.

The checked-in code-review and fast-evaluation evidence describe the earlier
overhaul and retain their original scope and UTC windows. They are historical
evidence, not fresh measurements of the enlarged incident collection.

## Runner and quality gate

```sh
uv run python scripts/run_evals.py --mode fast --repeat 5 --require-repeatable \
  --out /tmp/cra2-policy-fast.md
uv run python scripts/run_evals.py --help
```

The runner defaults to `fast`, with one repeat and a minimum score of 10.
Every repeat is scored, and any assessment below `--min-score` fails the gate.
The current calibration cases require `status: "assessed"`; an unexpected
`needs_clarification` earns zero rubric points and fails even at a zero threshold.
Its questions and null risk values are reported without a scorer crash.
A requested but unavailable System 2 result also fails, even if local fallback
matches the expected answer. With `--require-repeatable`, every case must have
identical status, score, level, review route, comments, questions, freeze state,
settings, and surfaced conflicts across at least two repeats. One repeat is
reported as **not assessed** for consistency. Matching repeated outputs are
sample observations, not a general proof of model determinism.

Exit codes are `0` for pass, `1` for failed quality requirements, and `2` for
invalid CLI options. Reports are still written on gate failure. The default
location is `docs/evidence/evals-<mode>[-<model>].md`; `--out` selects another path
and creates parent directories as needed. CI uses a temporary path to avoid
rewriting checked-in evidence on every test run.

Reports include exact UTC run windows, all-repeat accuracy and scores, per-case
score minima, the incident corpus size and SHA256, hashes of loaded rules/catalog/
team settings, and nearest-rank p50/p95 latency. Hashes identify the local inputs
without publishing raw team policy contents; they do not guarantee backend consistency.
The [enriched fast report](../docs/evidence/evals-enriched-fast.md) identifies
the 46-record corpus used before these policy changes. It and the original report
remain historical; current routes and settings require a new report.
The [policy report](../docs/evidence/evals-policy-fast.md) records the revised
routes, clarification-aware scorer, freeze verification, and team settings.
Timing covers each in-process
assessment, including failed provider calls, and excludes startup and report
writing. Hardware, scheduling, and sample size affect timings. No samples means
not measured, never an inferred zero latency.

## Provider and cost accounting

`auto` and `deep` can send context to Groq and incur charges. They require an
explicit mode selection in this runner. Provider caches are cleared before each
non-fast assessment, so repeat measurements exercise fresh responses.
Context may include selected sanitized user samples as well as synthetic
incidents, with at most five related records per assessment. The user authorized
the samples for this provider context; no live Groq calls were made for their
addition.

The report distinguishes System 2 selections, SDK request attempts, cache hits,
and failures. An SDK attempt does not prove provider receipt. Usage is included
when a response supplies it, even if validation rejects the response. Cached
responses do not rebill the original usage. Unknown usage stays unknown; no key
and a failed network request are not counted as successful model responses.

`--price-in` and `--price-out` must be supplied together as finite, nonnegative
USD-per-million-token rates. Zero is accepted only when explicitly supplied.
The report records those rates; the person running the evaluation must verify
and retain their source/date. Missing prices prevent a cost estimate. Missing
usage permits a labeled known-usage subtotal but prevents a complete per-1,000
assessment estimate. No provider request attempts means there is no provider-cost
sample; local operating cost is outside the report's scope.

These local token estimates are distinct from provider-complete measured costs,
Caveman inferred daily headroom, verified ledger savings, and the cost of
collecting evidence. A synthetic run cannot establish savings. Caveman review
requires a selected project, exact report windows, and attributable trace IDs.
No such telemetry was available during the code overhaul.
