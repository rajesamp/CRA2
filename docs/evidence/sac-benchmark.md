# SAC P0/P1 evidence — 2026-11-05

Scope: [issue #19](https://github.com/rajesamp/CRA2/issues/19), P0 baseline/design
and P1 validated semantic state. This is not a full/threshold/SAC comparison.

## Revision and reproducibility

- Baseline branch revision: `2edc8f637a40fffd25d807572e6c276411b45e48`.
- Measured implementation: `d86c7656063c7ad6bdf0f6d34959ba3568bdbb3a`.
- Source tree was clean when measured; the subsequent evidence commit changes
  only documentation/reports.
- Run: `0e3d55a158be47558ec4ebf4cfb2d4ab`, recorded at
  `2026-11-05T16:35:10.075304+00:00`.
- Dataset: `cra2-sac-baseline-v1`, seven cases, SHA-256
  `9ada80987861045bf3ac6422c702bfd4689c1e33ad18b45e5674f3e30b0169aa`.
- Source digest (95 source files):
  `be809814220a9b1582ee6a4bd4a39435cc37791c82622262fcaaae7f5fa6588d`.
- Configuration digest:
  `e8b4313904c114f1c34a032b12d14ab48f8a224515f4f862c2428c13c27fbdff`.

[Machine-readable report](sac-baseline.json) includes individual measurements,
source-file hashes, loaded policy/catalog/rules digests, Python version, fixture
version, fixed seed/configuration and all parity checks. Reports use exclusive
file creation, so reproduction requires a new output path.

## Measured P0 results

| Observation | Result |
| --- | --- |
| Observer-off/on pairs | 35 (7 cases × 5 repeats) |
| Workflow executions | 70 |
| Parity/repeatability/expected-status failures | 0 across 70 executions and 35 pairs |
| Observer off, p50 / p95 wall latency | 21.76 / 35.26 ms (n=35) |
| Observer on, p50 / p95 wall latency | 22.37 / 30.61 ms (n=35) |
| Live provider requests | 0 |
| Provider/model identity | Not applicable, local evidence mode |
| Tokens, peak context, cost, compaction overhead, risk agreement | Not measured (null) |

The workload uses fixed synthetic retrieval, actual in-process read-only tool
functions and an isolated empty preference store. It covers local change review,
health, dependencies, unconfirmed freezes, approval refusal, missing service and
tool failure. It bypasses MCP transport and embedding retrieval. Timings include
graph construction and local work, were taken on a developer machine alongside
test activity, and have no confidence interval. The lower observed p95 with
observation enabled is noise, not evidence of a speed improvement. Node timings
are nested; do not add them to request time. No SAC savings or quality parity can
be inferred.

## Regression and reducer evidence

| Gate | Result |
| --- | --- |
| Root offline suite, before implementation | 502 passed, 4 live tests deselected |
| Root offline suite, after implementation | 502 passed, 4 live tests deselected |
| Final Week 2 suite | 343 passed in 54.81 seconds |
| New focused P0/P1 suite (included above) | 102 passed |
| Fast evaluation | 20 cases × 5 repeats = 100 assessments; minimum/mean 10/10 |
| Risk levels, routes, citation rubric | 100/100 each |
| Repeatability | Same decision context for 20/20 cases across all five repeats |
| Fast evaluation provider requests | 0 |
| Diff whitespace check | Passed |

[Fast evaluation details](sac-regression.md) preserve rubric outcomes, data hashes
and missing-usage labels. The final P1 review tightened three boundaries: policy
references cannot masquerade as historical evidence; one tool result's references
must share its digest; and stale state cannot rewind execution against an advanced
host ledger. Tests also cover strict versions/types, UTF-8 size limits, duplicate
JSON keys, credentials, unknown evidence/actions, service/policy substitution,
source/ledger tampering, tool fact promotion, deterministic replay and mutation
isolation. Existing citation, policy-floor, advisory-only, CLI, app, Slack and
memory tests remain unchanged.

## Reproduction and environment notes

```sh
uv sync --locked
uv sync --locked --project week2
PYTHONPATH=. uv run --locked --offline pytest -q -m "not live"
TMPDIR=/tmp uv run --locked --offline --project week2 python -m pytest week2/tests -q
PYTHONPATH=. uv run --locked --offline python scripts/run_evals.py \
  --mode fast --repeat 5 --require-repeatable --out /tmp/cra2-sac-regression-new.md
uv run --locked --offline --project week2 python scripts/benchmark_sac.py \
  --repeat 5 --out /tmp/cra2-sac-baseline-new.json
```

Initial setup needed two uncached packages from the existing Week 2 lockfile;
dependencies and lockfiles were not changed. On this macOS environment, direct
installed-script execution did not resolve the editable `cra2` package. The
explicit `PYTHONPATH=.` prefix above resolved root test/evaluation imports.
`TMPDIR=/tmp` keeps test preference databases inside MemoryStore's allowed paths.

The first Week 2 run had 240 passes and one Slack integration failure because
the fresh checkout lacked the local retrieval index. The documented public model
download returned HTTP 403. An existing local archive was verified against the
repository's pinned SHA-256 and 76,692,531-byte size, then the documented offline
`python -m week1.setup_index` built 57 documents, 68 chunks and 46 incidents. The
unchanged Slack test and final complete suite passed. Model/index artifacts remain
ignored under `week1/.cache`; neither their bytes nor personal filesystem paths
are published here. A fresh machine still needs the pinned model artifact.

## Outstanding issue #19 work

- P2: integrate fresh per-action contexts, `full|threshold|sac` opt-in modes,
  externally resolved evidence/policy, runtime budgets, deadlines and cancellation.
- P3: genuine multi-step three-mode comparison, recovery/integration adversarial
  cases, provider usage and end-to-end compaction overhead. Paid provider testing
  needs separate authorization.
- P4: measured publication results and Substack follow-up, after those experiments.

The reducer remains standalone; its state cannot authorize deployments. Host
authority and raw evidence stay external, and digests do not substitute for trusted
validation or signed provenance. No default behavior, persistent preferences or
production deployment was changed.
