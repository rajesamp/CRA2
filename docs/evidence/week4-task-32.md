# Task 32 — actual local fault demonstrations

2026-10-31. Reproduce from repository root:

```sh
TMPDIR=/tmp week2/.venv/bin/python -m week4.faults --out /tmp/cra2-faults.json
```

[Actual nine-case transcripts and correlated traces](week4-task-32.json):
**9/9 passed**, zero provider requests, no model rating, stale result or crash.
Canonical corpus/data and actual owner records are untouched.

| Fault | Actual fallback | Tool attempts / failures | Result |
|---|---|---|---|
| health-invocation-timeout | tools_unavailable | 1 / 1 (measured) | Pass |
| ambiguous-reference | needs_clarification | 0 / 0 (not_accessed) | Pass |
| no-matching-evidence | insufficient_evidence | 2 / 0 (measured) | Pass |
| policy-changed-inflight | context_changed | 2 / 0 (measured) | Pass |
| configured-team-changed | memory_unavailable | 0 / 0 (not_accessed) | Pass |
| required-rail-unavailable | guardrails_unavailable | 0 / 0 (not_accessed) | Pass |
| metadata-capacity | telemetry_unavailable | 2 / 0 (measured) | Pass |
| source-version-changed-inflight | tools_unavailable | None / None (unavailable) | Pass |
| corpus-index-absent | retrieval_unavailable | 0 / 0 (not_accessed) | Pass |

The health timeout crosses a real MCP boundary: a temporary child handler
sleeps during the actual admitted health call. Its six-second client deadline
records one attempted/failed invocation. This differs from task 26's timeout
before initialization, which correctly recorded zero invocations.

Source mutation uses an injected version change after one real graph call;
the result is not inserted or served. Its fallback does not invent invocation
counts when the cache wrapper cannot preserve measured accounting. The probe
separately records the one actual call. Policy/preference mutation uses
isolated actual SQLite memory. Missing corpus/index uses a missing temporary
path; no canonical file is removed. Required-rail failure is injected at the
actual NeMo SDK method. Full telemetry retains its original row; nothing is
deleted to recover capacity. All fault traffic is labeled evaluation.

Fault review reproduced two accounting gaps before fixing them: discarding
a stale answer lost actual completed-call metrics, and help omitted explicit
no-access metrics. Safe fallbacks now retain actual tool/provider accounting
without stale outputs. A third regression showed policy-file team identity
could change while memory stayed bound to the original team. Startup team
identity is now pinned; changing it requires a fresh trusted process, and
identity is checked before reading/writing preferences. Mutable policy fields
within the same team remain authoritative per request.

Verification: failing regression proofs were committed before fixes; **20
focused accounting/telemetry/dashboard/cache tests passed** (26.54 s), followed
by the actual 9/9 fault runner. Final milestone scorecards and regression gates
are rerun after these late fixes; earlier scores are retained as history.

Learning: a safe fallback must withhold unsafe/stale content and preserve the
truth about work already performed. Cache/policy identity checks protect
correctness even when the source changes during execution. A process's trusted
team identity is different from a mutable risk preference.
