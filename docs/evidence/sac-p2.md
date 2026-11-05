# SAC P2: bounded action execution evidence

Date: 2026-11-05. Scope: P2 of [issue #19](https://github.com/rajesamp/CRA2/issues/19).
Branch: `feat/sac-action-loop`, stacked on P0/P1 draft PR #20.
Runtime implementation: `3066d62`; CI and explicit integration gates: `35e658a`.
Documentation/evidence changes after these revisions do not change runtime code.

## Delivered behavior

- No selector/environment setting: existing routing, batched tools, payload and
  public output remain on the legacy path.
- Explicit `full`, `threshold`, `sac`: the same selected, bounded action plan,
  with fresh validated contexts and deterministic reduction after each action.
- Local change: retrieve, health, dependencies; Groq adds exactly one assessment.
  Tool-only requests dispatch only their selected read-only tool.
- Policy, raw evidence and action ledger remain host-owned. Source `#` anchors,
  global document scope, exact citation membership, risk floors, unconfirmed
  freeze semantics, human-only approval and read-only Slack preferences persist.
- Step/byte/output-token/deadline ceilings and cancellation prevent later actions.
  Cancellation checks at reviewer entry and SDK dispatch block new late requests
  after slow client setup. Already-dispatched operations may finish; their late
  results are discarded. No retry or fail-open fallback was added.
- Admin trace receives only fixed labels and numeric metrics. Raw semantic state,
  ledger, registry, history, owner records and callbacks are excluded.
- New Week 2 CI runs the complete offline suite on Python 3.10/3.13. Real-encoder
  coverage remains an explicit, non-skipping gate outside the default CI suite.

## Executed local gates

Python: 3.13.15. Dependencies came from existing lockfiles; no dependency or
lockfile changes. No live Groq or Slack call was made.

| Gate | Observed result |
| --- | --- |
| Root offline tests | 502 passed, 4 live cases deselected; 6.69 s |
| Week 1 tests (locked Week 2 environment) | 494 passed; 8.32 s |
| Final full Week 2 offline suite | 450 passed; 54.01 s |
| New default-suite cases | 107 added across context, execution, lifecycle, presentation, dispatch and baseline isolation |
| Explicit real-encoder Slack integration | 1 passed; 16.76 s |
| Explicit real-source P2 combinations | 6 passed; 24.29 s |
| Fast evaluation | 20 cases × 5 repeats = 100 assessments; minimum/mean 10/10 |
| Fast levels/routes/citation rubric | 100/100 each; 20/20 cases repeatable across all five runs |
| Fast provider request attempts | 0 |
| Whitespace/diff check | Passed |

[Raw fast evaluation](sac-p2-regression.md) contains data/configuration hashes,
measurement window and every case outcome. The real-source gates verify the
checksum-pinned BGE/FastEmbed artifact, build fresh SQLite indexes from the actual
corpus, and use actual MCP subprocess tools. Groq responses are explicitly injected
fixtures. Six P2 cases cross all modes with local and provider-assisted routing;
they assert global `service=None` evidence is not relabeled and missing token
usage stays null.

## Review findings resolved

Independent review reproduced late provider dispatch after an abandoned compose
worker and after delayed SDK-client initialization. Synchronization-based tests
now block both paths and confirm timeout tightening at dispatch. Review also
found observer byte totals that omitted the replacement assessment input; tests
now compare event totals with prepared provider message-content bytes.

Additional regressions cover exact freshly sent policy/evidence allow-lists,
malformed usage/identity/timing metadata, cross-service/source tampering, budget
exhaustion, unsupported actions, concurrent reused graphs, frozen policy sources,
and poisoned tool-event metadata. No raw provider result can become state or
untyped public telemetry. The first full run found an environment-setting leak in
the newly added CLI test; restoring that test's environment fixed eight downstream
failures without weakening existing expectations. The final full run passed.

## Reproduction

Unset `CRA2_CONTEXT_MODE` for baseline/default regression commands. The historical
P0 harness now refuses to run when that setting could mislabel its workload.

```sh
PYTHONPATH=. uv run --locked --offline pytest -q -m "not live"
TMPDIR=/tmp uv run --locked --offline --project week2 python -m pytest week1/tests -q
TMPDIR=/tmp uv run --locked --offline --project week2 python -m pytest week2/tests -q
TMPDIR=/tmp uv run --locked --offline --project week2 python -m pytest week2/integration -q
PYTHONPATH=. uv run --locked --offline python scripts/run_evals.py \
  --mode fast --repeat 5 --require-repeatable --out /tmp/cra2-sac-p2-regression-new.md
```

`PYTHONPATH=.` addresses this machine's editable-package import issue; `/tmp`
keeps local test stores inside the existing permitted roots. Standard CI requires
no ignored model/index cache. Explicit real-encoder tests fail if artifacts are
missing/invalid and never download them. See [coverage boundaries](../../week2/integration/README.md).

## Limits and next milestone

This remains a short host-selected workflow with zero or one model action.
Full history here means validated action observation records with references;
it is not a raw transcript baseline. All modes retain the same necessary sources.
The experiment does not establish long-running SAC effectiveness, model quality
parity, latency gains, token savings or cost savings.

Per-action bytes measure prepared contexts; the assessment charge covers system
prompt plus serialized user payload. HTTP/schema framing is excluded. Aggregate
prepared bytes include non-model actions, so they are not provider token usage.
Input tokenizer counts remain unknown; the provider's output-token limit is
enforced separately. Objective bounds remain the strict P1 2,000-character/no-
control contract for explicit experiments, with safe refusal rather than truncation.

P3 remains: genuine repeated-model workloads, matched three-mode datasets,
tokenizer/provider usage, end-to-end overhead, failure/recovery and quality
evaluation, with separate authorization for paid calls. P4 publication follows
those measured results. Merge/review of parent PR #20 precedes merging this
stacked implementation; no production deployment or automatic approval is included.
