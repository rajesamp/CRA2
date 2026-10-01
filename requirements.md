# CRA2 requirements: Week 1 scope

This is CRA2's scoped adoption of [ChangeRiskAdvisor requirements](https://github.com/abhineer/Sep-Projects/blob/3e52f28ae1f430211d2df6098ab366f38ebdb86e/ChangeRiskAdvisor/requirements.md), read at upstream commit `3e52f28ae1f430211d2df6098ab366f38ebdb86e` (file blob `a7029bf3b7e9983dcfa1bcc80833fd03887f3513`). The source remains authoritative for the four-week project. This document paraphrases its acceptance needs and identifies the Week 1 boundary; it is not a claim that later weeks are implemented.

## Scope and precedence

Week 1 delivers a usable Gradio chat, local retrieval over incidents/postmortems/runbooks, a cited historical risk discussion, and the written planning artifacts. The existing CRA2 CLI, code, tests, data, dependencies, and prior documents are preserved. The optional implementation lives in `week1/`; additional documentation appears below and in `docs/`. Existing safeguards remain active even though the upstream schedule introduces a fuller guardrail layer later.

The source persona is Sameer (also called Sam). CRA2 already uses Raj Sam. These are labels for the same demo role: a DevOps engineer reviewing proposed changes. The existing persona is retained; neither persona is evidence of a customer interview. The 16 original synthetic incidents and 30 separately approved sanitized samples keep their provenance. This later authorization supersedes the earlier synthetic-only meeting proposal without treating the samples as current operational truth.

## Week 1 acceptance requirements

| ID | Requirement | Evidence expected |
|---|---|---|
| W1-R01 | Accept a natural-language change description through Gradio; ask for service/details when ambiguous | Successful detailed-query transcript and a clarification example |
| W1-R02 | Retrieve bounded passages from a corpus containing incident summaries, postmortems, and runbooks | Corpus inventory, stable chunk/source identifiers, visible retrieved passages |
| W1-R03 | Chunk and embed locally, persist vectors, and rank the query against that store | Ingestion counts, model identity, dimensions, corpus digest, top-three results |
| W1-R04 | Ground risk discussion in retrieved evidence; never treat similarity as proof of shared causation | Cited response, source inspection, unsupported-evidence fallback |
| W1-R05 | Remain advisory; never issue an approval, block, merge, or deployment action | Approval-request refusal and an explicit human-decision reminder |
| W1-R06 | Distinguish historical/static samples from current health, freezes, and dependency observations | Week 2 boundary responses; no invented current facts |
| W1-R07 | Keep credentials out of prompts, displayed responses, logs, index, and share configuration | Exact-known-key guards, scoped regression checks, blocked local file serving |
| W1-R08 | Provide a narrative six-pager, customer/internal PR/FAQ, and team/stack record | Draft artifacts plus genuine team review/read confirmations, tracked separately |
| W1-R09 | Provide a reproducible launch path and observable demo evidence | Local URL, UI screenshot, setup/run record; public sharing and team posting require actual evidence |

## Six upstream query intents

| Source query | Week 1 response contract | Later dependency |
|---|---|---|
| 1: checkout configuration risk | Retrieve relevant checkout incidents. An unspecified change gets questions; a detailed follow-up gets cited historical concerns | Current health lookup: Week 2 |
| 2: similar previous changes | Show specific matching passages, preserving service/type/provenance; clarify an unresolved reference | Broader corpus quality work remains ongoing |
| 3: freeze status now | Say current applicability cannot be confirmed from this static corpus | System-health/freeze tool: Week 2 |
| 4: payment-gateway dependents | Explain verification boundaries without inventing edges or claiming a live lookup | Callable dependency graph: Week 2 |
| 5: remember a high-risk service | Explain that this demo does not persist conversational preferences | Two-session team memory: Week 2 |
| 6: approve the change | Decline to decide or execute; offer an evidence-backed assessment for a human | The advisory boundary applies now and later |

## Deferred requirements and acceptance limits

Tools/MCP, live health/freeze/dependency observations, conversational team memory, tool traces, operational caching, dashboards, and full six-query end-to-end evaluation belong to Weeks 2–4. Existing implementations that resemble those features are retained but do not establish their upstream acceptance evidence. Static team JSON is not a two-session memory demonstration; a local graph lookup is not an MCP round trip.

Week 1 embeddings/retrieval do not establish production accuracy. Citation membership does not prove semantic correctness, and a model seed does not guarantee identical fresh wording. No risk indication is assigned when evidence or a usable provider response is missing. Local evidence mode shows passages without a model rating. A localhost URL is not a public share link; a draft is not team agreement.

See [tasks](tasks.md), [Week 1 launch instructions](week1/README.md), and the [alignment evidence](docs/evidence/week1-alignment.md) for implementation and acceptance status.

## Question-scope clarification — 2026-09-30

W1-R01 applies to CRA2 change requests, not every message entered into chat. Classify supported CRA2 tasks before consulting history or evidence. Preserve valid help, dataset queries, change clarification, historical comparison, and advisory/Week 2 boundaries. A recognized CRA2 task takes precedence over unrelated chatter without answering the unrelated portion.

Unrelated or unsupported questions, including an app-username request, receive one fixed response with the CRA2 GitHub link and no further answer, incident evidence, or model request. Scope cannot be inferred from an earlier service discussion or a bare mention of CRA2. W1-R07 credential checks continue to run before classification; the app must not discover or disclose usernames or secrets to answer account questions. [Verification](docs/evidence/week1-question-scope.md) records the tested forms and limitations. This adds no Week 2 implementation.
