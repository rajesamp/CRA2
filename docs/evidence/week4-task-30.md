# Task 30 — measured fix and comparable rerun

2026-10-31. The unchanged original 18 cases improved **16/18 → 18/18**,
88.89%→100% (+11.11 percentage points), with zero provider attempts. Both
improved rows are the diagnosed approval paraphrases. This is synthetic
contract pass rate, not model accuracy.

[Baseline](week4-task-28-baseline.json) · [After application fix](week4-task-30-after.json).
Case, scorer-module, corpus/index, tool, team-policy and lockfile identities
match across these two reports. No frozen input/label/scorer was edited to
produce this improvement. Four new regressions first failed and were committed
before the runtime fix. Five alias/negation/description checks plus the existing
help/preference/support tests passed: **78 focused tests** (52.93 s).

The shared bounded intent predicate now recognizes greenlight/sign off/common
authority requests. Detailed changes receive explicit refusal plus permitted
review; bare aliases refuse without external work. Quoted/negated examples and
ordinary deployment descriptions are distinct; anchored preference notes stay
inert. This remains bounded language handling, not general intent recognition.

Initial reserved sanity checks scored **2/4**; their original inputs and report
remain unchanged. Both misses were overly narrow status labels for valid
existing help/listing responses. [Label review](week4-task-30-label-review.md)
documents a separately named manifest revision with stronger content checks.
[Corrected reserved validation](week4-task-30-reserved-v2.json) scored **4/4**
without another application change. This label correction is not counted as
application improvement. These inspected, same-author cases are regression
evidence; independent human-labeled/live-model quality remains unmeasured.

The runner gained an explicit alternate-manifest option for that separate
validation. An AST comparison against the frozen baseline confirms the `score`
function itself is unchanged. The original 16→18 reports retain their original
matching full scorer-module hashes.

Actual request/tool/provider accounting, baseline then after: [{"requests": 20, "measured_mcp_attempts": 15, "provider_attempts": 0}, {"requests": 20, "measured_mcp_attempts": 15, "provider_attempts": 0}].
Raw per-request times remain in both reports. The after run overlapped focused
verification, so no isolated latency delta is inferred from those heterogeneous
cases. Task 23 retains the dedicated four-condition cache latency evidence.
No change in cache correctness or provider demand is claimed from this fix.

Learning: preserve failed reports, change the narrow application cause, and
keep label corrections distinct from quality gains. Uncertainty and residual
measurement limits belong beside the score.
