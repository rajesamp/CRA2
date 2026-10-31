# Task 20 — actual local NeMo integration

2026-10-31. NeMo 0.24.1 resolved in the existing Week 2 environment; 18 packages
added, no existing locked package version changed. FastEmbed remains 0.8.1.
The actual encoder fingerprint equals the persisted index fingerprint:
`fastembed-artifacts-sha256:6df0bb4a5b7e0d3b1524076116a802509249de2cea5c8b1be7a443d66b7d4338`.

`week3/guardrails.py` executes registered local actions through NeMo's real
`LLMRails.check_async`, with no configured model. The host checks retrieved
context using an input rail; this is not NeMo-managed retrieval. Each request
owns its engine and exports bounded stage/verdict events, not internal history.
UI, CLI and offline Slack adapters share the graph. Missing/failed checks stop
the protected path. Existing host metadata and argument/result gates remain.

Verification (actual, TMPDIR=/tmp for the existing memory-path contract):

- Initial feature test failed with missing `rails`, then passed after wiring.
- `week2/.venv/bin/python -m pytest week3/tests/test_guardrails.py week2/tests -q`: **245 passed** (57.07 s), including actual custom-action allow, context rejection, output approval rejection and required-check failure. NeMo emits a vendor deprecation warning; it is not a failed test.
- Root offline core gate: **502 passed, 4 live tests excluded** (4.72 s).
- Unchanged Week 1 suite in the Week 2 environment: **494 passed** (6.76 s).
- Fast core calibration: **100/100**, 20 cases × 5 repeats, zero provider attempts. This is calibration, not general answer quality.
- Actual CLI payment-dependents query completed with NeMo input/output verdicts and an MCP stdio graph result.

An initial test invocation used the OS temporary directory, which the existing
memory contract rejects; rerunning with the project's required TMPDIR=/tmp
resolved those environment-related failures without weakening the path check.
No model/provider request, Slack delivery or public deployment was performed.
Browser screenshots belong to task 25. Task 21 still owns detailed approval
continuation and the mechanism-support probes.

Learning: NeMo checks messages; LangGraph routes work; MCP transports read-only
tool calls. Local custom actions avoid classifier model costs but only enforce
explicit bounded checks; this does not prove semantic safety for all language.
