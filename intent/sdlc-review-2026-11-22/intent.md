# Intent: CRA2 corrections and DevOps feature priorities
Author: CRA2 owner (originator); Codex (drafting agent). Status: draft.

Review date: 2026-11-22. Candidate baseline: `de338ae3fa4650fa8153850edf47f1402ec4051d`.
This is Stage 1 discovery, not an accepted design or implementation plan.

## Problem

The owner asked to apply AI-Native SDLC to CRA2 and “come up with features and
corrections required”. Earlier requests include historical incidents, automated
rollback impact analysis, deployment-note language analysis, dynamic dependency
graphs, peer reviews, safe change-request uploads and a live dataset view.
The owner also wants NeMo enforcement, guardrail activity for “Current session
only”, and evaluations using Ragas or TruLens.

CRA2 has a working owner demo and tested draft enhancements. However, a green
regression suite does not establish broad injection resistance, semantic answer
quality, verified rollback readiness or capacity for 1,000 active users.
The deployed V1 image and the draft incident/guardrail features are distinct.

## Proposed outcome

Produce a traceable correction backlog and a DevOps feature backlog, then let
the owner accept a delivery slice before detailed design or code changes.

The proposed sequence, subject to the adjacent HERMETIC review, is:

1. Close reproduced context-filter gaps; bound admission/queues; align release
   and product documentation; expand evaluation and audit evidence.
2. Build evidence-backed recovery analysis: what an image rollback cannot undo,
   which compatibility/reconciliation checks are missing, and what test would
   resolve each uncertainty. Attach a versioned review evidence bundle.
3. Add controlled incident/change ingestion and V2 uploads through quarantine,
   human promotion and immutable dataset versions; then expose the V3 explorer.
4. Add timestamped DevOps signals, a dependency graph with source/age per edge,
   and concurrent-change conflict scenarios. Load/cost gates precede wider access.
5. Trial note-quality cues, peer-review incentives and durable long-running
   workflows. Treat UTCP as a measured adapter experiment, not an assumed upgrade.

See [findings and feature cards](findings.md) for evidence, prerequisites and
checkable completion conditions. Fixes, features and experiments are labelled
separately; no customer value or market novelty has been established yet.

## Affected users and systems

- Owner reviewing changes; future explicitly invited DevOps/SRE reviewers.
- Protected Gradio app, public introduction, LangGraph workflow and MCP tools.
- NeMo custom actions, local BGE retrieval, isolated TruLens evaluation and CI.
- Durable preference/audit storage, release evidence, data ingestion and future
  read-only CI/CD/observability connectors.

## Constraints

- Keep the protected app owner-only and invitations on hold until explicit
  approval. The public introduction contains no identity or private evidence.
- Keep guardrail activity current-session-only. Never expose raw flagged prompts,
  account identities or owner audit records in that panel.
- Remain advisory: no automatic deployment, rollback, approval or dataset promotion.
- Keep source facts, historical examples, declarations and unknowns distinct.
  Incident-only records cannot support change-failure probability.
- Preserve user edits and existing tests. A bug fix needs a failing regression
  test committed before the fix, after the design/plan gates are accepted.
- Keep artifact signing, scan controls, least privilege, controlled egress and
  existing audit retention. No new public resource identifiers or account emails.
- Do not enable an external model judge or new data transmission implicitly.
- Prior planning target is USD 10/month, currency previously assumed. Its current
  applicability to the expanded product and actual all-service spend are unknown.
- No product changes, Cloud Run rollout, merge, account grant or invitation are
  authorized by this review artifact. A later accepted delivery slice governs them.

## Open questions

1. Accept this correction/feature scope and the first slice, or change priorities?
2. Which source should supply the first approved real change/outcome records,
   and who owns service mapping, data permission and label review?
3. What are the target peak concurrent reviews, latency/error SLO and revised
   total monthly budget before expanding beyond the owner demo?
4. Does “agent substrate” mean durable workflow execution, a particular product,
   or an autonomous agent runtime? This review assumes only durable execution.
5. The referenced `sentinel-mcp-tool-poisoning` skill was not found in the local
   skill inventories searched. Resolve the policy mapping explicitly; existing
   fixed MCP inventory validation is not evidence of a separate SENTINEL runtime.

Acceptance is pending. Per the invoked skill, the originator reviews/corrects
this intent before its Stage 1 commit; accepted intent is the input to Stage 2.
Do not backdate acceptance of the existing draft PRs.
