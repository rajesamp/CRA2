# Intent: finish CRA2 Week 2 with LangGraph and MCP

Author: Raj Sam (originator); captured by Codex. Status: task 15 authorized in chat.
Date: 2026-10-16.

## Completion authorization — 2026-10-17

The owner explicitly authorized finishing tasks 16–18 end to end without
interruptions or further approval stops, with surgical edits only and no
mutation outside the CRA2 work directory and `/tmp`. This authorizes the
remaining previously proposed task sequence, local state, tests, UI and evidence.
It supersedes per-task confirmation stops for this scoped completion run.
Keep private learner notes ignored. Do not publish, deploy, change global
configuration, install outside the permitted directories, or modify unrelated
working-tree edits. Use the already installed environment and browser runtime.

## Scope clarification — 2026-10-17

The originator reaffirmed the goal: review the final task-plan objective,
prepare LangGraph, and complete Week 2 one task at a time with private
`task_xx_learner.md` explanations. Keep these notes in ignored
`private-learning/`; they are not publication artifacts. Update each note with
actual changes, exercises, evidence, and remaining limits as its task progresses.
The missing Sentinel skill/substitute decision remains unresolved; reaffirming
implementation scope does not constitute approval of that exception.

## Problem

"i have to complete my rest of week 2 tasks. lets introduce langgraph and task where i have to implement MCP"

Tasks 12–14 delivered tool contracts and callable health/dependency functions.
The chat does not yet invoke them through MCP. Persistent team preferences,
cross-session recall, and an operational trace panel remain tasks 16–18.

## Proposed outcome

Complete the remaining tasks in order, discussing each before implementation:

- Task 15: use an explicit LangGraph workflow to coordinate the existing
  retrieval/provider logic and a local stdio MCP client/server exposing only
  `check_system_health` and `get_dependency_graph`. Record actual tool discovery,
  calls, validated results, and an advisory agent response grounded in them.
- Task 16: define team-scoped preference storage and record write/read evidence.
- Task 17: demonstrate permitted preference recall across two separate sessions,
  without weakening authoritative policy or risk floors.
- Task 18: show sanitized actual tool events and recalled preferences in an
  expandable Gradio panel; record a screenshot.

## Affected users and systems

CRA2's local Gradio application, orchestration adapter, existing Week 2 tools,
isolated dependency environment, local ignored state, tests, and task evidence.
Reuse existing modules rather than rewrite retrieval, provider, or tool logic.

## Constraints

- Keep advisory-only behavior, deterministic question routing, credential checks,
  evidence grounding, and configurable `week1/responses.json` responses.
- Snapshot provenance remains explicit; call time never establishes freshness,
  current production health, active incidents, or verified freeze applicability.
- Gate tool metadata before it enters model context and validate calls/results
  at execution boundaries. Fail closed on screening or protocol errors.
- Enforce tool allow-lists, bounded calls, finite deadlines, protected errors,
  team isolation, and credential-free traces/checkpoints.
- Preserve existing root dependency files and unrelated working-tree changes.
  Resolve compatible locked dependencies in an isolated environment.
- No deployment/approval authority, production connector, Jev integration,
  Week 3–4 work, or inferred Week 1 human acceptance.

## Open questions / prerequisites

### Task 15 authorization — 2026-10-17

After presentation of the implementation plan and bounded metadata-screening
substitute, the owner instructed: "lets start the with 15 Langgraph orch + both
tools through MCP". Proceed with task 15 using the proposed exact-descriptor
gate. This is a bounded substitute for these two local tools, not a claim that
the unavailable Sentinel skill was restored. Tasks 16–18 remain subsequent work.
The prerequisite history below is retained; the task 15 gate is resolved by
this follow-up authorization.

- `/Users/rajeshsam/Downloads/AGENTS.md` requires the
  `sentinel-mcp-tool-poisoning` skill for MCP metadata registration. It is absent
  from the supplied skill catalog and was not located in the local agent skill,
  Codex skill, or plugin-cache skill inventories. Restore the skill or explicitly
  authorize a reviewed substitute before task 15 implementation.
- The same AGENTS.md requires presenting success criteria and a plan/diff, then
  confirmation before application. The AI-Native SDLC skill also requires
  acceptance of intent before the design/build stages.
- Proposed task 15 acceptance: both tools traverse MCP; known/unknown service,
  malformed arguments, rejected metadata, timeout, and unavailable-source cases
  have protected outcomes; agent answers cite returned provenance; existing
  Week 1 regressions remain passing.
- SDK versions, graph state shape, storage backend, and the exact file-level
  implementation plan follow in the specification after intent acceptance.
