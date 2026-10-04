Beyond Vectors · SRE/DevOps build · Snapshot 27 Sep 2026

# ChangeRiskAdvisor weekly tracker

<!-- Historical snapshot from the rajesamp/CRA export, preserved unedited. Current CRA2 status starts at "CRA2 update". -->

Progress on the 34-task core plan, judged only from evidence committed to the [rajesamp/CRA](https://github.com/rajesamp/CRA) repo. Refreshed every Sunday before the 8:00 CDT check-in.

Plan [tasks.md](https://github.com/abhineer/Sep-Projects/blob/main/ChangeRiskAdvisor/tasks.md) Owner **Raj Sam** (solo build) Updated **27 Sep** Now in **Week 2**

Nearly there

## Week 1: 5 of 11 done, the other 6 built and waiting on a key or approvals

- **Done by the definition of done:** kickoff, dataset, corpus, ingestion and retrieval (tasks 1 and 6 to 9).
- **Waiting on a Gemini API key:** the system prompt, prototype and Gradio tasks (5, 10, 11) are built and tested, and need one run with model access to record their evidence.
- **Waiting on people:** team approval of PR #1 (PR/FAQ) and PR #2 (6-pager), then a teammate’s fresh-clone run.

## All 34 tasks

DonePartialNot started

Next

## What closes Week 1

A model key and three approvals stand between the current build and a closed Week 1.

### One command closes three tasks

Set GOOGLE_API_KEY*→*run_evidence.py (#5, #10)*→*app.py screenshot + share link (#11)

Add a Gemini API key in .env, run uv run python scripts/run_evidence.py, then launch app.py and capture a grounded answer.

### People steps, in order

1\. Team approves and merges PR #1. 2. A teammate clones main and records a fresh-clone run. 3. Team approves PR #2.

### Then Week 2

Tool specs (#12), the health and dependency tools, MCP, and team memory.

Outside the plan

## Other findings

- docs/adr/index.md lists ADR-001 to ADR-006, but none of the six files exist, so every link is broken.
- The architecture journal's last entry (21 Sep) predates the repo bootstrap.

Week over week

## History

| Snapshot | Done | Partial | Not started | Note |
| --- | --- | --- | --- | --- |
| 27 Sep | 5 | 7 | 22 | End of day: dataset, corpus, ingestion, retrieval done; prompt, agent, UI built; 6-pager complete; model evidence and approvals pending. |

Source of truth: docs/progress.md in rajesamp/CRA. A task counts as done only when the evidence named in tasks.md is committed to the repo. Week dates assume the Sunday check-ins on 20 Sep, 27 Sep, 4 Oct and 11 Oct.

---

## CRA2 update — 30 Sep 2026

The text above is the original Claude export, preserved as a historical snapshot of `rajesamp/CRA`. This update tracks [rajesamp/CRA2](https://github.com/rajesamp/CRA2), using [CRA2 task status](../tasks.md) and its recorded evidence. The previous repository, Gemini instructions, Week 2 label, counts, and ADR findings are historical; they are not current CRA2 conclusions. The export supplied the tracking structure, not the original webpage URL or its interactive state. No scheduled refresh has been configured by this update.

**Week 1 engineering delivery: complete. Human acceptance: pending. Weeks 2–4: deferred.** Owner closure does not replace the plan's individual acceptance checks.

| Task | Current delivery | Remaining acceptance / qualification |
| --- | --- | --- |
| 1. Roles, requirements reading, stack | Draft recorded | Confirm owners, reading, and stack |
| 2. Six-pager | Draft recorded | Team review and agreement |
| 3. Release and FAQ | Draft recorded | Team review and agreement |
| 4. Repository and runnable setup | Implemented | Independent teammate fresh-clone run |
| 5. Advisory prompt and demo cases | Implemented; recorded model demonstration | [Local demo evidence](evidence/week1-demo.md) |
| 6. Incident, graph, and health dataset | Foundation present | 16 synthetic plus 30 sanitized incidents; six catalog services have multiple synthetic incidents, two have one |
| 7. Corpus | Added | Six derived postmortems, five runbooks, and incident records |
| 8. Chunking, embeddings, persisted index | Implemented; ingestion recorded | [Retrieval evidence](evidence/week1-retrieval.md) |
| 9. Relevant top-three retrieval | Documented checkout cases verified | Scoped retrieval checks, not universal quality |
| 10. Grounded free-text assessment | Implemented; routing fixes merged | [Latest scope verification](evidence/week1-question-scope.md) |
| 11. Gradio demo, screenshot, sharing | Local demo and historical screenshot recorded | Public sharing and team-channel posting pending |

### Changes since the original snapshot

- The Gemini-key blocker does not apply to CRA2. A real Groq assessment and the advisory-boundary case were recorded on 28 Sep. No key is included in this tracker.
- Dataset listing, counts, projections, capabilities questions, and question scope now have routing regressions. Capabilities and unsupported-question fixes were merged in [PR 11](https://github.com/rajesamp/CRA2/pull/11) and [PR 12](https://github.com/rajesamp/CRA2/pull/12).
- Latest recorded checks: 449 Week 1 tests, 402 core tests with four live tests excluded, and 100/100 fast core evaluations. These are bounded checks, not general classifier accuracy.
- Existing screenshots document the earlier live demo; they do not verify the latest revision's rendered appearance.
- Jev remains outside this work. Session-history display remains an ADR proposal, without implementation.

### What remains

1. Confirm team roles, requirements reading, and stack.
2. Record team agreement on the six-pager and PR/FAQ.
3. Record an independent teammate's fresh-clone run.
4. Choose and record public demo sharing and the team destination.

### Later weeks

| Week | Tasks | Status |
| --- | --- | --- |
| 2 | 12–18: operational tools, MCP, memory, trace UI | Deferred; no milestone acceptance recorded |
| 3 | 19–25: guardrails, caching, metrics, six-query validation | Deferred; existing core features do not constitute this milestone's acceptance |
| 4 | 26–34: observability, evaluations, measured fixes, dashboard, final demo | Deferred; existing test results do not constitute this milestone's acceptance |

### History addition

| Snapshot | Milestone | Acceptance | Scope |
| --- | --- | --- | --- |
| 30 Sep 2026 | Week 1 engineering complete | Human confirmations and sharing pending | CRA2; Weeks 2–4 deferred |

The original 27 Sep Done/Partial/Not started counts used the CRA snapshot's definition of done. They have not been carried forward as CRA2 counts or rewritten as full acceptance.

<!-- Week 2 tasks 12–18: continuation after the preserved Week 1 snapshot. -->
## CRA2 Week 2 continuation — 30 Sep 2026

The owner authorized tasks 12–18 and accepted the task 12 contract proposal in
chat, with each later task discussed before implementation. The earlier Week 2
deferral is historical. **Week 1 engineering remains complete; its human
acceptance remains pending. Week 2 is in progress.**

| Task | Current delivery | Remaining evidence |
|---|---|---|
| 12. Tool contracts | [Spec delivered](tools.md): inputs, outputs, errors, grounded examples | Verification recorded with the task 12 change; tool execution is not claimed |
| 13. System health | Pending discussion | Known/unknown-service test log |
| 14. Dependency graph | Pending discussion | Known/unknown-service test log |
| 15. MCP round trip | Pending discussion; required Sentinel skill unresolved | Actual agent response and tool trace |
| 16. Memory schema | Pending discussion | Schema and write/read log |
| 17. Two-session recall | Pending discussion | Both session transcripts |
| 18. Expandable agent trace | Pending discussion | Screenshot of actual calls and recalled policy |

PR #13 is merged; [response-catalog evidence](evidence/week1-response-catalog.md)
records 494 Week 1 tests, 402 core tests, and 100/100 repeated fast assessments.
Those checks preserve Week 1 behavior; they do not establish Week 2 tool,
memory, or UI acceptance. Task 12 adds documentation and Week 2 comments above
its signatures and tracking sections, with no runtime code changes. Jev remains
outside scope. Weeks 3–4 remain deferred.

<!-- Week 2 tasks 13–14: latest implementation status, preserving earlier snapshots. -->
## CRA2 health and dependency tools — 30 Sep 2026

**Tasks 13 and 14: executable local tools implemented and verified.**
[Recorded calls and tests](evidence/week2-tools.md) show known/unknown-service
behavior. The shared module is 165 lines, with Week 2 comments and no new
dependencies. It labels fixture facts as synthetic snapshots; active incidents,
freshness, and current freeze applicability are not invented.

Verification: 100 focused tool tests, 502 total core tests (four live tests
excluded), 494 Week 1 tests, and 100/100 repeated fast evaluations passed.
MCP/chat integration remains task 15; memory and the UI trace remain tasks
16–18. Week 1 human acceptance and Jev's exclusion remain unchanged.
