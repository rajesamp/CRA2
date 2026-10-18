# Spec: CRA2 Week 2 completion with LangGraph and MCP

Author: Codex. Status: task 15 authorized to implement in chat on 2026-10-17.
Date: 2026-10-17. Input: [intent](intent.md), clarified by the originator.

## Requirements

Completion run authorization: the owner approved tasks 16–18 without further
interruptions and restricted all mutations to CRA2 and `/tmp`. Implement the
design below using the existing environment. Use local evidence by default;
team identity is trusted host configuration, never an editable browser field.
Support only explicit bounded preference commands, fail closed on unavailable
memory, preserve configured policy even when explicitly false, and expose
conflicts. Store policy notes as inert text; never pass them as model instructions.
No durable chat-history feature is introduced.

1. Task 15 exposes both existing tools through local stdio MCP. A LangGraph
   workflow invokes them and uses validated results in an advisory response.
2. Preserve source provenance: fixtures are synthetic snapshots, freshness and
   active incidents stay unknown, and freeze reports are not current calendar
   observations. The upstream requirement permits static/lightly simulated data.
3. Reject unapproved metadata before model context or invocation. Enforce input
   and result validation, finite deadlines, bounded calls, and protected errors.
4. Task 16 documents and verifies durable team preference writes/readback.
5. Task 17 recalls preferences in a new session for the same configured team;
   another team must not read or change them. Conversational text cannot select
   a different team. A local single-team demo is not multi-tenant authentication.
6. Task 18 renders actual calls and recalled settings in an expandable Gradio
   panel, with a real expanded-panel screenshot.
7. Preserve Week 1 behavior, credential protection, advisory output, authoritative
   policy, and configurable responses. No extra provider call for routing.
8. Maintain ignored `private-learning/task_12_learner.md` through
   `task_18_learner.md`. Distinguish existing evidence, current verification,
   planned exercises, and failures. Verify every file is ignored and untracked.

## Design

### Final goal and current boundary

The full 34-task plan ends in an evidence-backed advisory demo with memory,
tools, guardrails, caching, evaluations, observability, and a recorded rehearsal.
This change completes only Week 2 (tasks 12–18). Weeks 3–4 retain their own
acceptance, even where existing code already implements similar safeguards.

### Task 15: explicit graph and MCP transport

Use a small `StateGraph` with ordinary Python nodes and conditional edges.
The graph is the host orchestrator; MCP is the tool transport. Reuse the
existing health/dependency functions, retrieval, routing, and provider adapters.

Flow: validate input and credentials -> classify supported task -> resolve
service -> retrieve when required -> invoke allow-listed MCP tools when required
-> compose a grounded response -> guard output -> return sanitized trace.
Unsupported/help/clarification/advisory-boundary paths terminate before tool or
provider calls. Pure tool queries do not need retrieval or Groq. A detailed
change assessment exercises both tools, retrieval, and the configured reviewer.
Tool results enter the assessment evidence explicitly, rather than merely being
appended to an answer generated without them.

State includes question, session-local context, selected service/intent,
retrieved evidence, validated tool results, resolved policy/preferences,
sanitized events, and final answer. Do not persist raw conversations or full
graph state: durable chat history remains deferred under ADR-002.

The MCP server exposes exactly `check_system_health(service_name)` and
`get_dependency_graph(service_name)`. A fixed local module launch uses the
isolated environment's interpreter, no shell, minimal child environment, and
no provider/UI credentials passed to the server. Protocol output goes to stdout;
private exception bodies never reach the user or trace.

Use the official MCP Python client lifecycle: initialize, discover, validate
inventory, invoke, validate results, close. Bound the complete session and calls
with cancellation and child-process cleanup; limit discovery/result sizes.
Check returned tool identity, requested service, status/error shape, allowed
fields, source provenance, and evidence identifiers before use.

Proposed substitute for missing Sentinel skill, pending explicit authorization:
an exact canonical comparison against reviewed descriptors (name, description,
input/output schema and accepted annotations), exactly two unique tools, and
revalidation before invocation. Reject duplicates, extra tools, unknown fields,
schema additions, changed descriptions, and discovery failures. Store reviewed
descriptors locally in source, never derive the allow-list from server metadata.
This gate is bounded to these two tools and is not a general semantic scanner.
It does not claim cryptographic binding of the executing server implementation.

Use isolated `week2/pyproject.toml` and `week2/uv.lock`; resolve compatible
LangGraph, MCP, Gradio, retrieval, and test dependencies without changing root
or Week 1 locks. Verify actual resolved SDK APIs before implementation. Do not
invent versions or assume latest examples match the installed API.

### Tasks 16–17: application memory, separate from checkpoints

Use a small SQLite application store in ignored `week2/.local/`, with schema
version, configured team identity, known service, high-risk preference,
freeze-policy notes, provenance, and update timestamp. Parameterized queries,
bounded validated fields, protected errors, and atomic upserts are required.
Missing storage can produce an explicit empty preference result; malformed,
locked, or failed storage must produce an unavailable result, never empty.

Accept explicit supported preference writes; do not infer memory writes from
retrieved content, tool output, or model output. Retry-safe upserts must not
silently remove stored flags. No arbitrary SQL, paths, or team IDs from chat.
Freeze notes are policy text, never proof of an active freeze.

Apply recalled preferences explicitly during policy resolution; retain
authoritative configured policy and existing risk floors. Any conflict must be
visible. A stored high-risk flag must remain visible even if the risk model
fails; local evidence mode still issues no model risk rating. The current
configured high-risk policy uses a medium assessment floor; changing that
mapping is a separate policy decision, not implicit in memory persistence.

Demonstrate two separate sessions with the same team/store and a negative
cross-team case. Durable graph checkpoints are unnecessary for this acceptance
and would persist more data than required.

### Task 18: same chat experience, expanded evidence

Provide an additive `week2/app.py` entry point based on the existing Gradio UI.
It calls the Week 2 workflow, preserves review modes and protection settings,
and renders an expandable panel with actual calls/results, source uncertainty,
recalled preferences/provenance, and protected failure statuses. Do not stream
raw graph state, SDK objects, prompts, chain of thought, or secret-bearing
environment values. A session ID is generated by the host, not supplied in chat.

## Policy conformance

- Preserve baseline files and existing tests; new runtime/locked environment
  lives under `week2/`. Keep historical task/evidence records append-only.
- Respect `/Users/rajeshsam/Downloads/AGENTS.md`: review gate, scoped changes,
  credential secrecy, fail-closed execution and required metadata interception.
- Apply God Mode security principles at tool boundaries. Cloud image, IAM,
  signing and admission controls belong to any future deployment; this local
  change provisions no infrastructure and claims none of those controls.
- Follow the project's uv workflow and SDLC artifact/review stages. Never claim
  user acceptance or completed tests from proposed documentation.

## Flagged concerns

Task 15 update: the owner's follow-up instruction to start task 15 after review
authorizes the proposed two-tool descriptor gate and implementation plan.
Historical concerns 1–2 below are resolved for task 15; the live-provider and
Git-ignore qualifications still apply. Tasks 16–18 are not implemented here.

1. Required `sentinel-mcp-tool-poisoning` skill is missing. An explicit substitute
   decision is pending; do not implement MCP as though that requirement vanished.
2. File-level plan and this design await owner confirmation before runtime work
   under AGENTS.md. Scope authorization is not a fabricated signed design review.
3. Live provider validation needs the configured provider to be reachable.
   Offline test doubles prove integration paths, not a successful Groq response.
4. Notes remain ignored, but `git add -f` can override Git ignores. No ignore
   configuration can prevent a deliberately forced addition; never force-add.

## References

- Local upstream plan: `../Sep-Projects/ChangeRiskAdvisor/tasks.md` and its
  `requirements.md`; CRA2 policy/acceptance: repository `tasks.md` and
  `requirements.md`.
- [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)
  documents state, nodes, edges and compilation. Its private state channels are
  not automatically redacted from streams; render an explicit event projection.
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
  distinguishes per-thread checkpoints from cross-thread application stores.
- [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
  is the implementation reference; installed APIs and versions require checks.
