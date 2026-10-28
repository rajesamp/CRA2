# Plan: CRA2 Week 2 with LangGraph and MCP

## Admin trace panel plan — 2026-10-18

1. Add focused regression proof for adjacent tabs, locked trace callbacks,
   any-four-digit demo validation, session reveal/lock, and history lifecycle.
2. Change only Week 2 presentation: server-side demo state, masked/cleared
   input, and the trace components inside Admin. Gate chat/selection/undo/clear
   projections as well as visibility. Keep private audit and agent execution
   unchanged. Update local help to direct users to Admin. If the existing
   semantic guard mistakes navigation for an attack, allow only a whole bounded
   navigation question and verify appended actions still block.
3. Run the focused checks and Week 2 suite. Verify in Chrome that locked
   responses do not serialize trace facts, earlier modes survive unlocking,
   locking/fresh sessions clear the view, and chat/cooldown still work. Use an
   explicit offline reviewer for Groq rendering, with actual local MCP/retrieval.
4. Record evidence/private learning and restart only the owned port-7862 app.
   No new provider request, dependency or unrelated mutation.

Result: implemented and verified. Final Week 2 gate: 196 passed in 44.49 seconds.
Chrome proved four-turn history across both modes with an offline reviewer,
actual MCP/retrieval and memory recall; lock/reveal, isolated fresh sessions,
retry/undo/clear and 15,677 ms cooldown recovery passed. Final live app proof
at 18:51:18 UTC passed Admin navigation, local evidence, both MCP tools, memory
recall, earlier-turn selection and private-file HTTP 403. The app is running
on port 7862 and the fixture is stopped. No provider request or dependency added.

## Abuse guard implementation plan — 2026-10-18

1. Create a synthetic labeled collection, validate splits/schema, and reuse the
   installed BGE model. Compare majority/nearest-prototype baselines and choose
   a threshold on validation before reporting held-out results. Record errors.
2. Add a separate bounded owner-only SQLite store and local read CLI; protect
   permissions, paths, schema, credentials and unavailable/corrupt storage.
3. Gate chat before any graph call, add independent prohibited-action checks,
   retain benign out-of-scope records, and keep private verdicts outside traces.
4. Add server-client cooldowns, centered notice and timer-driven UI recovery.
   Block refresh/session/header bypass. Preserve earlier UI behavior.
5. Verify the store/gate with fast tests, then a real classifier/browser run
   proving 15 seconds, recovery, private-file denial and persisted owner records.
   Run Week 2 checks, update private learner/evidence, and restart the owned app.

## Trace history and app help plan — 2026-10-18

1. Reproduce missing app-help coverage, missing earlier trace selection and
   obsolete chat badges with focused regressions.
2. Add bounded Week 2 help routing/copy using the existing catalog and parser.
3. Retain guarded per-turn traces in Gradio session state, add a selector and
   original-mode labels, and remove chat badges. Preserve retry/undo/clear.
4. Verify both modes with an offline reviewer, actual MCP/retrieval and browser
   selection of an earlier turn. Run the Week 2 gate, update evidence/private
   learner notes, and restart only the owned app process on port 7862.

## Presentation correction plan — 2026-10-18

1. Add a failing regression for the owner's exact question in both modes,
   using actual MCP transport and a clearly labeled offline reviewer double.
2. In `week2/workflow.py`, retain validated assessment level/questions in trace;
   keep rating floors and all execution paths unchanged.
3. In `week2/app.py` and its response catalog, project concise outcomes for
   assessment/memory/failure replies, retain supporting response details inside
   the trace, and label both views with the visible turn number. Collapse
   supporting details and reset trace on clear/undo. Remove demo instructions
   and internal configuration hints from the primary UI.
4. Run focused regressions and the Week 2 gate, then verify consecutive turns,
   trace labels, clear/reset and recalled memory in a real local browser.
   Verify Groq rendering offline; do not make a new provider request.
5. Update the ignored task 18 learner note and record actual evidence. Restart
   only the CRA2 app process previously launched for this chat.

Status: tasks 15–18 complete; task-specific evidence, browser proof and final regression checks recorded. Date: 2026-10-17.
Inputs: [intent](intent.md), [design](spec.md), tasks 12–18.

Completion run: tasks 16–18 are now authorized without intermediate confirmation.
Implement task 16 storage/schema first; task 17 explicit writes, recall and policy
integration second; task 18 loopback Gradio UI, real two-session browser workflow
and screenshot last. All generated databases, test temporaries, browser profile
and captures stay inside the work directory or `/tmp`. No dependency/global
configuration changes are needed. Run final unchanged regression suites and
update each private learner note plus task-specific evidence before close-out.
WIP limit: one task at a time; no multi-agent implementation requested.

Final task 18 result: additive `week2/app.py` with the same chat experience,
host-owned session state, projected execution events and a collapsed trace
panel. Actual browser inspection found and corrected a component relocation
issue before the final screenshot. The corrected chat and trace are visible
side by side. Existing root/Week 1 runtime and locks were preserved. All
completion-run writes stayed inside CRA2 or `/tmp`; browser/server validation
processes were closed after capturing evidence. No dependencies were installed
and no new provider call was made during tasks 16–18.

Tasks 16–17 implementation note: added `week2/preferences.py` and
`week2/tests/test_preferences.py` to keep explicit command parsing and policy
precedence separate from storage/graph transport. The single task-15 deferred
memory expectation was updated to the authorized write behavior with an isolated
store; no unrelated tests were weakened. MCP child processes disable bytecode
writes and use `/tmp` for temporaries to honor the completion-run mutation scope.

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
# Useful-answer correction plan — 2026-10-18

1. Reproduce the exact reported prompts in focused regressions using actual
   MCP calls and an offline reviewer; forbid live Groq in validation.
2. Update only Week 2 presentation and response copy, with a targeted
   clarification copy in the workflow. Derive numeric facts from the user's
   explicit values, normalize time units, and omit ambiguous comparisons.
3. Retain all diagnostics in the same trace and keep Local evidence only as
   the browser default. Do not add Slack history to Admin.
4. Run the focused checks and Week 2 regression gate, verify the real browser,
   update evidence/private learner notes, and restart only this chat's owned
   web and Slack processes so both use the corrected presentation.

Result: seven failures reproduced before the fix; 239 full Week 2 checks passed,
then 53 focused checks passed after two added numeric edge cases. The actual
browser verified the five reported turns and preserved Local mode, both MCP
calls and trace correlation. Both owned processes were reloaded. No live Groq
request or Slack test message was sent. Evidence:
`docs/evidence/week2-useful-answers.md`.
