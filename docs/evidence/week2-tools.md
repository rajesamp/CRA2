<!-- Week 2 tasks 13–14: actual local tool checks; MCP and UI integration are task 15 onward. -->
# Week 2 tool implementation evidence

Owner authorization: proceed with tasks 13 and 14, after the task 12 contract
was merged in PR #14. Implementation follows [the contracts](../tools.md), in
one additive [module](../../week2/tools.py), with [focused tests](../../tests/test_week2_tools.py).

## Task 13 — system health

The health tool reads and validates the canonical synthetic snapshot on every
call. It retains reported freeze uncertainty and unknown active incidents and
freshness. Inputs, source contents, and outputs pass the existing known-key guard,
including configured UI credentials. Errors expose codes without input values,
private paths, or exception bodies. No model or production lookup is involved.

Initial focused verification, before implementing task 14:

```text
uv run --locked --offline pytest -q tests/test_week2_tools.py
47 passed in 0.33s
```

Tests cover known and unknown services, invalid/missing/extra arguments, bounded
source reads, malformed/nonfinite/duplicate-key JSON, record/edge validation,
credential canaries including escaped JSON values, and reading changed health
rather than returning a cached snapshot. This is scoped offline verification,
not production health evidence or a general secret-detection claim.
