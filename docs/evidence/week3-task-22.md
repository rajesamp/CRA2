# Task 22 — bounded exact caches

2026-10-31. Browser/Slack host callbacks now reuse a host-owned cache object;
low-level workflow callers can explicitly inject `WorkflowCaches`. Separate
CLI processes do not share an in-process cache. Exact hashed identities include
trusted team/store scope and authoritative policy/preference state; relevant
source/index/encoder/contract/implementation versions are checked on reuse
and again before the final response. Policy is loaded from its authoritative
file per request; in-flight preference or source changes discard the result.

Three bounded caches: query vectors (24 h), retrieval and synthetic tool results
(5 min); each has 1,024 entries and 16 MiB serialized-value budget. This does not
claim a 16 MiB process-memory ceiling: Python/key/runtime overhead is additional.
Per-key bounded single-flight avoids duplicate work without a global work lock.
No final-answer cache, failed-result caching, Redis or implicit source freshness.

Verification:

- **9 cache tests passed** (8.20 s): absolute expiry without sleeps; copies and
  eviction; failure/in-flight mutation rejection; sync/async single-flight;
  actual MCP reuse; team/preference changes; distinct numeric queries; source
  fingerprint change; actual local query-vector/retrieval reuse and a mutated
  temporary index rejected instead of replaying cached content.
- **42 focused cache/app/workflow/useful-answer tests passed** (26.64 s) before
  the final additional index-mutation test. Existing tests were preserved.
- [Actual four-request record](week3-task-22.json) shows tool-query miss/hit and
  concrete-change miss/hit, with actual tool result counts **1 → 0** and
  **2 → 0**, fresh request IDs, layer events and zero provider attempts.

An actual cache hit emits `cache_result`, not a fabricated tool result. The
client still performs its existing discovery/pre-invocation metadata checks
on every actual RPC. Cache hits validate the reviewed local contract and source
versions without starting a child merely to reproduce a lookup. Unsupported
custom retrievers use their existing injection path without guessed caching.

Learning: TTL controls retention; source versions control validity. Neither
turns a synthetic snapshot into observed production truth. A cleared or changed
preference changes the dependent cache scope immediately; fresh policy is still
read and checked before output. Task 23 measures latency; these checks alone
make no speed-up claim.
