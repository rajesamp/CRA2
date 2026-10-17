# Plan: CRA2 Week 2 with LangGraph and MCP

Status: task 15 complete; local/MCP tests and one explicitly authorized live Groq assessment verified. Date: 2026-10-17.
Inputs: [intent](intent.md), [design](spec.md), tasks 12–18.
WIP limit: one task at a time; no multi-agent implementation requested.

## Files that change

New runtime, introduced only in its corresponding task:

| Task | Files | Purpose |
|---|---|---|
| 15 | `week2/pyproject.toml`, `week2/uv.lock` | Isolated, resolved dependencies |
| 15 | `week2/contracts.py` | Reviewed descriptors and validation |
| 15 | `week2/mcp_server.py`, `week2/mcp_client.py` | Local MCP transport and guarded execution |
| 15 | `week2/workflow.py`, `week2/responses.json` | LangGraph host and configurable Week 2 answers |
| 15 | `week2/tests/test_mcp.py`, `week2/tests/test_workflow.py` | Protocol, failure and grounding tests |
| 16 | `week2/memory.py`, `week2/tests/test_memory.py`, `docs/memory.md` | Schema and write/read behavior |
| 17 | `week2/workflow.py`, `week2/tests/test_workflow.py` | Preference write/recall and policy integration |
| 18 | `week2/app.py`, `week2/tests/test_app.py`, `week2/README.md` | Chat UI, expanded trace and launch guide |

Append task-specific evidence to `docs/evidence/week2-task-15.md` through
`week2-task-18.md` and status sections to `tasks.md` and
`docs/weekly-tracker.md`. Add a README launch section once verified. Preserve
unrelated existing documentation edits and the untracked learning curriculum.

Private local files: `private-learning/task_12_learner.md` through
`task_18_learner.md`, ignored using an appended `.gitignore` rule. Memory under
`week2/.local/` and the Week 2 virtual environment are ignored too.

## Order of work

1. Review final project goal and existing task evidence. Prepare learning notes
   for tasks 12–14; mark their checks historical until rerun.
2. Resolve the mandatory Sentinel skill/substitute decision. Confirm this design
   and file-level plan under AGENTS.md; commit accepted stage artifacts in order.
3. Task 15: resolve/lock dependencies, implement descriptor validation and the
   stdio MCP server/client, then compile the explicit workflow. Review SDK APIs
   against the resolved versions. Keep raw graph state ephemeral.
4. Verify task 15 with actual MCP subprocess calls, known/unknown services,
   rejected metadata/schema mutation, duplicate/extra tools, malformed results,
   missing source, deadlines and cleanup. Confirm both outputs actually influence
   the agent response. Label offline and live-provider evidence separately.
5. Explain task 15 changes in its learner note and record bounded acceptance.
6. Task 16: discuss/store schema, implement validated team-scoped SQLite storage,
   verify actual write/read and protected failure behavior. Update its note.
7. Task 17: discuss allowed writes/conflict behavior, integrate memory, run two
   separate sessions, and prove cross-team isolation plus policy preservation.
   Update its note with the actual transcripts and how recall differs from RAG.
8. Task 18: discuss panel fields, connect the Gradio UI to the workflow, verify
   genuine trace contents, and capture the expanded panel on a real local query.
   Update its note with the screenshot and source/secret limitations.
9. Run relevant Week 2 checks, unchanged core/Week 1 regressions, and the existing
   repeated fast evaluation. Verify every learner file is ignored and absent
   from the index. Record checks without overwriting prior evidence.
10. Review the final diff against this plan, report deviations and remaining
    human acceptance. No automatic merge or public deployment.

## Risks and decisions

- Native MCP SDK versus adapter: choose direct SDK for the two-tool boundary;
  avoid a second integration abstraction unless the resolved SDK needs it.
- Explicit graph versus autonomous agent loop: choose bounded deterministic
  routing, preserving existing supported/unsupported behavior.
- Application store versus durable chat checkpoints: choose minimal team store;
  persistent chat history remains outside scope under ADR-002.
- Root environment changes versus additive environment: choose isolated Week 2
  lock; preserve current launch path and regression environments.
- Highest risk: lost policy precedence or ungrounded operational claims during
  workflow integration. Verify these explicitly, including failure paths.
- Unreviewed descriptors must never be admitted by accepting the server's own
  hash as the reference. Expected descriptors live in reviewed source.
- A local configured team identity is not production authorization. Do not claim
  secure multi-user hosting based on the single-team demo.

## Proof

### Task 15 implementation decisions and deviations

- Added `week2/__main__.py` and introduced `week2/README.md` during task 15,
  rather than waiting until task 18, to provide a reproducible protocol/graph
  entry point. The existing Gradio application remains unchanged.
- Pinned FastEmbed 0.8.1 after an actual stale-index failure with 0.9.0. This
  reuses the existing verified encoder identity without rebuilding its index.
- Added an explicit LangSmith dependency to disable environment-triggered
  tracing in a scoped context; no raw graph state is uploaded.
- Preserved Week 1's immutable historical-citation checks through a reviewer
  bridge: validate combined citations, retain tool citations in the exported
  trace, and pass historical citations to the existing adapter.
- Used real stdio and local-index runs, plus a clearly labeled offline reviewer
  double for assessment-payload proof. A provider attempt was unavailable;
  automatic approval review rejected a network-enabled retry because the exact
  data payload/destination lacked explicit authorization. The owner then
  explicitly authorized one assessment with that payload to Groq. That run
  succeeded; no further provider requests were made. See task-specific evidence.
- Root runtime/dependencies/tests and `week2/tools.py` were not edited.

Tasks count as done only after their named evidence exists. Preparation notes,
schemas without readback, direct Python calls, test doubles, and screenshots
without actual calls are not substitutes for their acceptance criteria.

Existing regression commands (rerun only once runtime work justifies them):

```sh
uv run --locked --offline pytest -q -m 'not live'
uv run --locked --offline --project week1 python -m pytest week1/tests -q
uv run --locked --offline python scripts/run_evals.py --mode fast --repeat 5 --require-repeatable --out /tmp/cra2-week2-fast.md
```

Proposed Week 2 check after that environment exists:

```sh
uv run --locked --offline --project week2 python -m pytest week2/tests -q
```

Verify `git check-ignore` and `git ls-files` for all seven learner paths before
any staging or publication. This preparation does not claim those runtime
commands have passed on new code.
