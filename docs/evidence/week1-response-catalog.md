# Week 1 configurable response catalog

Date: 2026-09-30 (America/Chicago). Baseline: `71806805fc78e0c8481997c948b0e4218803aab2`.

## Change

Fixed answer copy, capability labels, dataset field labels, and clarification templates moved from Python to [`week1/responses.json`](../../week1/responses.json). Exact documentation FAQ aliases can be added there without changing `chat.py`. One entry documents the existing session-history ADR boundary. No model writes the catalog at runtime.

[`chat.py`](../../week1/chat.py) now has 354 lines, down from 498. Dataset/evidence list rendering is in [`answers.py`](../../week1/answers.py); [`responses.py`](../../week1/responses.py) validates the catalog and renders templates. Existing callable/import bindings used by tests and callers are retained. The advisory reminder, task precedence, service resolution, policy floor, citation checks, canonical dataset facts, and source-hash checks remain in code.

The request reads one validated catalog snapshot and passes it to the router/renderers, preventing a mid-request edit from mixing versions. Later JSON-only edits need no restart after this implementation is loaded. Missing or invalid catalogs fail before retrieval or inference and produce the existing generic UI fallback. Known credentials are rejected in the catalog and questions without echoing them.

## Verification

- Before extraction: **449 Week 1 tests passed**.
- Final implementation: **494 Week 1 tests passed**, including 45 additional checks for JSON-only edits, FAQ aliases in both modes and three histories, precedence over configurable aliases, invalid/missing/oversized catalogs, duplicate keys/aliases, placeholders, and credential canaries. Existing tests were not rewritten.
- **108 comparisons** against the baseline chat implementation matched answers, traces, retrieval calls, and provider payloads: 18 declared existing questions × three histories × two modes, using injected collaborators and the same index path. This is preservation evidence for those cases, not unrestricted intent accuracy.
- **402 core tests passed**, four live tests excluded. Required fast evaluation passed **100/100** assessments, 20 cases × five repeats, minimum rubric score 10/10, repeatable decision context, and zero provider attempts. UTC evaluation window: `2026-10-01T01:47:58.922819+00:00` to `2026-10-01T01:47:59.004201+00:00`.
- Ruff static/format checks and Git whitespace checks passed for the changed Python files.
- Exact configured-credential scanning found zero matches in 98 tracked/non-ignored working files and one private UI log; a collector canary was detected. Coverage is those configured credential values and files, not arbitrary secrets or destinations.

## Limits

The catalog is trusted application content. Maintainers must review new questions and factual claims. Conservative FAQ decision/risk-label filtering does not establish semantic safety or evidence grounding for arbitrary text. Exact aliases are not a general classifier; unregistered phrasings may still receive the repository response. Existing supported tasks take precedence over FAQ entries, so modifying their copy uses the existing `messages` keys.

This refactor adds no operational tool, MCP, persistent memory, model, dependency, API credential, or Week 2 acceptance evidence. The earlier browser URL-policy rejection prevents a new automated rendered-screen claim; the UI handler and its generic failure path are covered offline.
