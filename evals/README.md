# Evaluation cases and methodology

`cases.json` holds 20 synthetic changes to the checkout system in `data/`.
These cases informed the rule weights, so they are calibration fixtures — not
a held-out test set and not evidence of production accuracy.

Incident context now includes the original 16 synthetic records plus 30
separately stored, sanitized user-provided samples: 46 context records, not
46 evaluation cases. The 20 calibration inputs stay assessable. Expected
routes express review attention: `routine-review`, `focused-review`,
`priority-review`. Removing the unconfirmed-freeze weight and high floor
deliberately changes CHG-04 to medium and CHG-08 to low; their freeze
questions and incident citations stay required. These are policy changes, not
edits to conceal a failing test. Added incident data alone never justifies
changing an answer.

Each case carries the structured `change`, the `expected` level and route,
desired comment tags (`flags`), acceptable incident citations (`cite_any`),
and a 10-point `rubric`.

| Check | Points | Full marks |
|---|---|---|
| level | 4 | Exact expected level; one level too high earns 1; other mismatches earn 0 |
| route | 2 | Exact expected advisory route |
| flags | 2 | Expected tags covered; proportional credit for partial coverage |
| cite | 1 | Every comment cites supplied evidence; a `cite_any` incident is cited when specified |
| format | 1 | Three distinct tags, no checked approval phrasing, rendered advisory sentence |

Citation checking verifies allowed-key membership. The rubric does not
establish whether arbitrary model prose is true or whether every unsafe
phrase is caught. Local output validation and policy regression tests provide
separate checks.

## Coverage and limits

The cases cover eight services, seven change types, and expected levels of
six low, nine medium, five high. Examples include unconfirmed freezes
(CHG-04, CHG-08), degraded direct dependencies (CHG-10, CHG-16), missing
rollback plans (CHG-01, CHG-12, CHG-13, CHG-20), config drift (CHG-01,
CHG-11), and deploy-order risk (CHG-05, CHG-13, CHG-19). They do not cover
live operational freshness or unseen production systems. Add independently
labeled, unseen changes before making generalization claims.

The added samples carry 28 external service labels. Retrieval can select
cross-service analogies with at least two meaningful shared terms; type match
alone never qualifies a candidate. Matches must not trigger the same-service
repeat-incident penalty. Regression coverage for selection order, bounded
context, provenance, and this distinction is separate from the 20-case
calibration score. A passing score — or a sample's mere presence — does not
prove its most relevant incident is retrieved.

The checked-in code-review and fast-evaluation evidence describe the earlier
overhaul and keep their original scope and UTC windows. They are historical
evidence, not fresh measurements of the enlarged collection.

## Runner and quality gate

```sh
uv run python scripts/run_evals.py --mode fast --repeat 5 --require-repeatable \
  --out /tmp/cra2-policy-fast.md
uv run python scripts/run_evals.py --help
```

The runner defaults to `fast`, one repeat, minimum score 10. Every repeat is
scored; any assessment below `--min-score` fails the gate. Calibration cases
require `status: "assessed"`. An unexpected `needs_clarification` earns zero
points and fails at any threshold; its questions and null risk values are
reported without a scorer crash. A requested but unavailable System 2 result
also fails, even when local fallback matches the expected answer.

`--require-repeatable` demands identical status, score, level, route,
comments, questions, freeze state, settings, and conflicts across at least two
repeats. One repeat is reported as **not assessed** for consistency. Matching
repeats are observations, not proof of model determinism.

Exit codes: `0` pass, `1` failed quality requirements, `2` invalid options.
Reports are written even on gate failure. Default location:
`docs/evidence/evals-<mode>[-<model>].md`. `--out` selects another path and
creates parent directories. CI writes to a temporary path so test runs never
overwrite checked-in evidence.

Reports include exact UTC run windows, all-repeat accuracy and scores,
per-case score minima, incident corpus size and SHA256, and hashes of loaded
rules/catalog/team settings. Hashes identify local inputs without publishing
raw policy contents; they do not guarantee backend consistency. The
[enriched fast report](../docs/evidence/evals-enriched-fast.md) identifies the
46-record corpus used before these policy changes; it and the original report
stay historical. The [policy report](../docs/evidence/evals-policy-fast.md)
records the revised routes, clarification-aware scorer, freeze verification,
and team settings. Timing covers each in-process assessment, including failed
provider calls, and excludes startup and report writing. Hardware, scheduling,
and sample size affect timings. No samples means **not measured**, never an
inferred zero latency.

## Provider and cost accounting

`auto` and `deep` can send context to Groq and incur charges; both need
explicit mode selection in this runner. Provider caches are cleared before
each non-fast assessment, so repeats exercise fresh responses. Context may
include selected sanitized samples plus synthetic incidents, at most five
related records per assessment. The user authorized the samples for provider
context; no live Groq calls were made to add them.

The report separates System 2 selections, SDK attempts, cache hits, and
failures. An SDK attempt does not prove provider receipt. Usage is recorded
when a response supplies it, even if validation rejects the response. Cached
responses never rebill original usage. Unknown usage stays unknown; no key
and a failed network request are not successful model responses.

`--price-in` and `--price-out` go together as finite, nonnegative
USD-per-million-token rates; zero is accepted only when explicitly supplied.
The report records the rates; the operator must verify and retain their
source/date. Missing prices prevent a cost estimate. Missing usage permits a
labeled known-usage subtotal but prevents a complete per-1,000-assessment
estimate. No request attempts means no provider-cost sample; local operating
cost is out of scope.

These local token estimates are distinct from provider-complete measured
costs, Caveman inferred daily headroom, and verified ledger savings. A
synthetic run cannot establish savings. Caveman review needs a selected
project, exact report windows, and attributable trace IDs. No such telemetry
was available during the code overhaul.
