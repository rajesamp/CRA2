# Intent: SAC foundations for issue #19

Author: Raj Sam (request), Codex (implementation record).
Status: implementation authorized by the request to deliver P0/P1 and a draft PR;
merge remains subject to human review.

## Problem
CRA2 has a bounded LangGraph workflow, not a multi-action model loop. Before
testing Single-Action Compaction, measure this baseline and establish a safe,
deterministic representation of execution state.

## Proposed outcome
Deliver P0 instrumentation, reproducible offline fixtures and ADR, plus P1
validated semantic state and deterministic reduction on `feat/sac-semantic-state`.
Link the draft PR to <https://github.com/rajesamp/CRA2/issues/19>.

## Affected users and systems
CRA2 contributors and the Week 2 workflow. Existing app, CLI and Slack behavior
must remain compatible.

## Constraints
No deployment approvals, paid live tests, new tools, persistent checkpoints,
preference changes, or claims of SAC savings. Preserve citation allow-lists,
policy floors, source provenance, and unconfirmed freeze semantics.

## Open questions
P2/P3 must establish a real per-action model boundary and comparable workloads;
this milestone cannot answer whether SAC improves cost, latency, or quality.
