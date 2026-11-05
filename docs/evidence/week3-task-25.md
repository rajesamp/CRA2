# Task 25 — visible badges and Week 3 close-out

2026-10-31. Actual browser verification used an isolated loopback app on port
7863, synthetic demo memory/audit storage under /tmp, Local evidence only, and
no provider calls. The existing app on its default port was not stopped.

- [Miss screenshot](week3-cache-miss.jpg): payment-dependents lookup, 0 reused / 1 lookup.
- [Hit screenshot](week3-cache-hit.jpg): identical repeat, 1 reused / 1 lookup.
- [Trace screenshot](week3-cache-trace.jpg): validated cache reuse, no new MCP
  call, and actual NeMo input/output checks.
- [Approval plus local review](week3-approval-review.jpg): explicit refusal,
  concrete 90% timeout-budget reduction, general review checks, no risk rating.
- Expiry proof: task 22's injected-clock test and task 23's 30 expired actual
  graph requests, all 30 returning to actual tool execution. No five-minute
  browser sleep or fake hit badge is used as proof.

The badge is per request. Help/blocked requests show not used; clear resets it;
undo restores the preceding turn. Trace history remains bounded and session
scoped, with reused tool facts distinctly labeled rather than fabricated calls.
The existing advisory reminder is preserved.

The first isolated launch could not bind inside the restricted execution
context; the loopback-only launch succeeded with reviewed local launch access.
The demo audit folder initially had non-private permissions and correctly
paused the request. Restricting the self-created folder to 0700 fixed setup;
no safety gate was weakened. The first paused request remains genuine history.

The broader test gate caught vague “approve checkout-service timeout change
now” incorrectly continuing review. Continuation now requires numeric before/
after detail or an explicit concrete change action, and never rewrites anchored
preference notes. Existing help tests were preserved; 61 focused checks passed.

Final Week 3 checks:

| Gate | Observed result |
|---|---|
| Week 2 + Week 3 suites, TMPDIR=/tmp | 257 passed, 81.43 s |
| Root core, excluding live tests | 502 passed, 4 excluded, 6.24 s |
| Unchanged Week 1 in Week 2 environment | 494 passed, 8.32 s |
| Fast calibration, 20 cases × 5 repeats | 100/100; zero provider attempts |
| Six-intent real local walkthrough | 6/6, including separate-process memory |
| Measured graph-query warm latency | p50 906.635 → 167.889 ms; 30/30 hits |

All seven Week 3 engineering tasks have named local evidence. NeMo's vendor
deprecation warning remains visible in tests. This does not establish live
model quality, general hallucination prevention or production freshness.

Learning: the badge is a presentation of actual execution state, not the
cache implementation itself. Tests prove expiry/isolation, measurements prove
speed, and a browser walkthrough proves what a user actually sees. Week 4
adds correlated telemetry, a broader frozen scorecard, error analysis and demo
readiness to this working foundation.
