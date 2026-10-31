# Task 23 — measured dependency-query reuse

2026-10-31. Reproduce from repository root:

```sh
TMPDIR=/tmp week2/.venv/bin/python -m week3.benchmark --out /tmp/cra2-cache-benchmark.json
```

[All 120 raw samples, warmups, environment and source identities](week3-task-23.json).
Four conditions interleaved, 30 measured requests each; imports, first request
and warmups reported separately. No outliers removed; no competing test jobs
were launched during measurement. This is a single local run, not a service SLA.

| Condition | n | p50 ms | p95 ms | Actual graph calls | Hits / eligible lookups |
|---|---:|---:|---:|---:|---:|
| Cache disabled | 30 | 906.635 | 960.739 | 30 | Not applicable |
| Enabled, empty before each request | 30 | 905.448 | 992.404 | 30 | 0/30 |
| Warm | 30 | 167.889 | 274.540 | 0 | 30/30 |
| Expired before each request | 30 | 906.688 | 1040.650 | 30 | 0/30 |

Warm p50 fell **81.48%**, from 906.635 to 167.889 ms (about 5.4× faster), while
actual graph calls fell 30→0. Expiry restored actual calls. Provider attempts
were zero. Disabled mode does not perform cache lookups; its hit rate is N/A.

Learning: a warm hit saves child startup/discovery/tool execution, while the
host still runs NeMo, policy and source/contract validation. Those retained
checks explain why a hit still takes time. p95 reports the slower tail, not
just the typical case. These numbers measure one graph query in this machine
and runtime; they do not measure model latency, production load or every layer.
Query-vector/retrieval hits are separately demonstrated in task 22.
