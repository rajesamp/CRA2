# Task 26 — correlated local observability

2026-10-31. [Actual success, cache-hit and MCP deadline traces](week4-task-26.json)
include one fresh request ID on every stage span, rail/cache event and actual
tool event. The host measures classification, memory, retrieval, tools,
composition, output, rail and cache timing. Reviewer timing is recorded only
when that adapter is invoked and identifies offline versus provider adapters.
No hidden reasoning or raw model log is exported.

MCP metrics count actual attempts, separately from workflow failures. The
concrete success attempted two tools; its cache-hit repeat attempted zero.
A real deadline before initialization produced `tools_unavailable`/`timeout`
with zero tool invocations, not an invented failed tool call. Metadata or
source failures with unknown attempt accounting are marked unavailable.

New compact local storage keeps only IDs, transport/status, bounded spans and
counts. Questions, answers, passages, memory notes and owner audit records are
excluded. The store requires private directory/file modes (0700/0600), has
2,000-row and 8-MiB limits, and never silently deletes records. Full/unavailable
storage returns a protected no-rating fallback. This is local bounded SQLite,
not WORM storage or production authentication. Transport labels separate
browser, Slack, CLI and evaluation paths; Slack messages were not sent.

Verification: **72 telemetry/MCP/Slack tests passed** (32.86 s), including real
protocol behavior and a triggered deadline, all-event correlation, cache-hit
accounting, metadata redaction, bounded storage failure and insecure/symlink
paths. A preceding 31 cache/app/workflow checks also passed. Three actual
records were persisted by the export probe; all local, zero provider attempts.

Compact record sizes for the three exported samples (bytes): [1249, 1153, 816].
These are serialized samples, not maximum process-memory or traffic claims.

Learning: an operation can fail before a tool is invoked. Reporting that as a
failed call would corrupt the denominator. Correlated events preserve the
difference, while a cache hit carries a new request ID and records reuse rather
than a repeated execution. Task 31 will turn these real counts into a dashboard.
