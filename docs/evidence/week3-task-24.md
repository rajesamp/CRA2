# Task 24 — all six local intents

2026-10-31. Actual local-index/MCP walkthrough: **6/6**. No live model
assessment or provider request. Reproduce from repository root:

```sh
TMPDIR=/tmp week2/.venv/bin/python -m week3.acceptance --out /tmp/cra2-six-intents.json
```

| Intent | Expected | Actual | Result |
|---|---|---|---|
| checkout | evidence_only | evidence_only | Pass |
| history | history_only | history_only | Pass |
| freeze | tool_evidence | tool_evidence | Pass |
| dependents | tool_evidence | tool_evidence | Pass |
| memory | write, separate-process recall, different-team empty | written; recalled in separate process; other-team empty | Pass |
| approval | advisory_boundary | advisory_boundary | Pass |

[Complete actual questions, answers and traces](week3-task-24.json). The memory
case uses three separate Python processes: explicit write, fresh-session recall
with no history or preference restatement, and different-team empty control.
Other cases use the actual local index and guarded MCP with eligible caching.
A cache hit is reuse, not a new tool call. Freeze state remains unknown for
current production use; local mode assigns no model risk rating.

Learning: an end-to-end contract check follows the user request through routing,
evidence, tools, policy, guardrails and presentation. Passing six cases does not
measure general language coverage or production accuracy. Week 4 adds a
versioned scorer, baseline, additional cases and error analysis; this narrow
walkthrough is a reusable input, not that entire milestone.
