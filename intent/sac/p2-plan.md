# P2: explicit bounded action execution

Authorization: continuation request to implement the next milestone of issue #19.
Base: P0/P1 draft PR #20; branch `feat/sac-action-loop` is stacked on that PR.

## Intent and design
Connect the validated state/reducer to real action boundaries without changing
the default CRA2 experience or increasing provider calls per assessment. Existing
requests (no selector/environment setting) retain the legacy full-context path.
Explicit `full`, `threshold`, or `sac` requests use one identical deterministic
plan: retrieve when needed, each selected read-only MCP tool, then one assessment
only in Groq mode. Local/tool-only requests never invoke a model. This is a
bounded host plan, not model-selected commands or repeated model assessment.

The host owns policy, original evidence and action ledger. Each action receives
a fresh validated context. Full retains validated action observations; threshold
clears retained observations at a configured byte threshold; SAC retains only
semantic state, current observation and independently resolved references. No
conversation transcript, preference note or raw provider response enters these
contexts. Existing compose/citation/policy gates remain the final authority.

## File-level plan
- `week2/context_builder.py`: bounded fresh context with source/policy resolution.
- `week2/execution.py`: per-invocation host coordinator, limits, action ledger,
  deterministic reductions, cancellation/deadline checks and safe metrics.
- `week2/workflow.py`: route only explicit experiments through action boundaries;
  preserve existing classification, preference handling and rendering gates.
- `week2/contracts.py`: inert source labels with fragments and distinct source
  service metadata, preserving global-document provenance.
- `week2/app.py`: trusted CLI context selector and sanitized trace summary; the
  normal chat layout and default review mode remain unchanged.
- `week1/provider.py`: optional trusted timeout/output-token ceilings that can
  only tighten configured limits; the default provider call remains unchanged.
- `cra2/system2.py`: optional host dispatch check immediately before the SDK
  call, preventing late requests after cancellation or slow client setup.
- `week2/tests/`: context/replay, boundaries, privacy, budgets, cancellation,
  failures, default parity and app/Slack integration.
- `.github/workflows/week2.yml`: locked offline tests on Python 3.10 and 3.13.
- `week2/tests/test_slack.py`, `week2/integration/`: actual SQLite/MCP/Slack
  integration with injected encoder in standard CI, and separate explicit real
  encoder gate retaining the original end-to-end assertions.
- `docs/adr-sac.md`, `week2/README.md`, `docs/evidence/sac-p2.md`: usage, trust,
  operational limits, actual verification and outstanding P3/P4 work.
- `scripts/benchmark_sac.py`: fail before work if an experimental environment
  setting would invalidate the legacy P0 baseline label.

## Budgets and failure behavior
Use bounded step count, per-context UTF-8 bytes, total dispatched input-byte
budget, model output limit through the existing provider, and a deadline. Bytes
are not called tokenizer counts. All tools remain the two reviewed read-only
tools. Failed validation, exhausted budget, timeout or cancellation prevents
later actions and returns a static unavailable/no-risk response. Synchronous
retrieval/provider collaborators run in workers; only the coordinator commits
state. In-flight read-only work may finish after local cancellation, but its late
result is discarded. Cancellation does not claim remote revocation.

## Proof and remaining scope
Run new focused tests, all root/Week 2 tests, the separate real-encoder Slack
gate, and five-repeat fast evaluations. Add CI with all original assertion
coverage preserved; do not silently skip a missing-model test. Tests must show
identical experimental action order across modes, no provider calls for local
requests, strict citation/floor preservation and isolation between requests.
P3 genuine multi-step comparisons, tokenizer/provider cost measurements and
separately authorized paid calls remain outstanding; no efficiency claims.

Review refinement: typed metadata checks apply both to returned reviews and to
provider failure accounting, so exception metadata is not a raw trace channel.
