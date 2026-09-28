# Week 1 team and stack agreement — draft

**Status:** Proposed coordination record. Actual member assignments, requirements
read receipts, stack agreement, and document reviews are **PENDING**. Creating
this file does not demonstrate that any teammate has read or agreed to it.

This document adapts Week 1 task 1 from the pinned [upstream task plan](https://github.com/abhineer/Sep-Projects/blob/3e52f28ae1f430211d2df6098ab366f38ebdb86e/ChangeRiskAdvisor/tasks.md)
and [requirements](https://github.com/abhineer/Sep-Projects/blob/3e52f28ae1f430211d2df6098ab366f38ebdb86e/ChangeRiskAdvisor/requirements.md).
Only tasks 1–11 are in this delivery scope. The full upstream requirements remain
context for later work, not a claim that Week 1 implements tools or memory.

## Persona naming

The upstream persona is **Sameer**; its shorthand also appears as **Sam**.
CRA2's established demonstration persona is **Raj Sam**. These new Week 1
documents use Raj Sam as the local alias for that same DevOps reviewer scenario.
This is a documentation mapping, not a claim that these are real teammates or
customers. Existing code, prompts, and documents retain their established names.

## Proposed responsibility split

The role categories follow the upstream plan so later work has a clear place,
but later-week implementation is not assigned to Week 1. A person may cover more
than one role once the actual team confirms the arrangement.

| Role | Week 1 responsibility | Later work, outside this scope | Confirmed member |
|---|---|---|---|
| Prompt and RAG owner | Advisory prompt, corpus design, ingestion, retrieval judgment, two manual prompt transcripts | Broader retrieval evaluation | **PENDING — unassigned** |
| Tools/MCP owner | Review the static graph/health fixtures and label them as snapshots | Health/dependency tools and MCP integration | **PENDING — unassigned** |
| Memory owner | Check that the demo does not claim to remember new preferences across visits | Persistent team preference memory and two-session verification | **PENDING — unassigned** |
| Guardrails/caching owner | Preserve current protections; check citations and the refusal to approve; review new data handling | Additional tool-aware guardrails and caching work | **PENDING — unassigned** |
| Observability/UI owner | Local Gradio workflow, ingestion/run evidence, screenshot and verified share-link record | Tool tracing and operational dashboard | **PENDING — unassigned** |
| Product/documentation coordinator | Reconcile Week 1 scope, coordinate narrative/PR-FAQ reviews, gather completion evidence | Subsequent planning after Week 1 acceptance | **PENDING — unassigned** |

No actual member names or attendance records were supplied for these assignments.
The product persona is not used to fill missing ownership information.

## Selected implementation stack and pending team agreement

The additive implementation lives in an isolated `week1/` uv project. These
technical selections describe the implemented prototype and recorded local
checks, not a completed team agreement or teammate acceptance run. Root dependencies and core CRA2 files
remain unchanged.

| Layer | Selected implementation | Current evidence | Team agreement |
|---|---|---|---|
| Language and local environment | Python 3.13 execution target; separate `week1/` uv project | [Project manifest](../week1/pyproject.toml) and [lockfile](../week1/uv.lock) | **PENDING** |
| Assessment baseline | Preserve the CRA2 library/CLI and its existing advisory policies | Current source, architecture, and offline tests | **PENDING** |
| Model provider | Optional protected Groq call selects citations and uncalibrated severity; UI shows source excerpts and fixed review questions, not model prose. Local-evidence mode has no model risk indication | [Chat adapter](../week1/chat.py), [provider adapter](../week1/provider.py), [demo evidence](evidence/week1-demo.md) | **PENDING** |
| Corpus | 11 new Markdown documents: six postmortems derived from synthetic CX incident facts and five runbooks; plus 46 existing incident records | [Corpus manifest](../week1/corpus/manifest.json); measured 57 documents and 68 chunks in [retrieval evidence](evidence/week1-retrieval.md) | **PENDING** |
| Embeddings | FastEmbed 0.8.1, `BAAI/bge-small-en-v1.5`, local 384-dimensional embeddings | Measured 68 stored embeddings, each 384 dimensions; model fingerprint in [retrieval evidence](evidence/week1-retrieval.md) | **PENDING** |
| Vector storage | Local SQLite vector store with cosine similarity | [Retrieval module](../week1/retrieval.py); stored count and judged top-three checkout probe in [retrieval evidence](evidence/week1-retrieval.md) | **PENDING** |
| UI | Gradio 6.28.0 local chat; public sharing requires explicit `--share` and `CRA2_UI_USER` / `CRA2_UI_PASSWORD` | [App module](../week1/app.py); local UI on port 7861; final screenshot tracked in [demo evidence](evidence/week1-demo.md), public share link pending | **PENDING** |
| Verification | Offline regressions, measured ingestion, judged retrieval, and bounded manual UI/provider checks | [Retrieval evidence](evidence/week1-retrieval.md), [demo evidence](evidence/week1-demo.md), and [task alignment](evidence/week1-alignment.md); no risk-calibration claim | **PENDING** |
| Branch workflow | Use a feature branch and a reviewable pull request against the existing repository | Proposed workflow; this record does not attest to a merge or team agreement | **PENDING** |

Two live model checks produced unsupported factual claims despite valid citation
IDs. The final UI therefore displays authoritative cited passages and fixed
human-review questions. Model severity and citation selection remain uncalibrated;
these technical checks do not establish semantic accuracy or team acceptance.

Week 1 new flows use static or explicitly simulated information. Existing CRA2
validation, credential safeguards, policy floors, and caching stay in place;
the upstream Week 1 simplification is not a reason to remove them. No new tools,
MCP integration, memory writes, live infrastructure checks, or deployment actions
are part of this scope.
The [README](../README.md) remains the fresh-clone entry point; its additive
Week 1 instructions must be verified by a teammate. No public share link or
team-channel post is recorded here. Sharing credentials must not be committed
or copied into screenshots, URLs, or transcripts.

## Actual confirmations

Replace pending entries only after the named member provides the confirmation.
Record the date and a review/message reference; do not infer agreement from a
file being present, an automated test passing, or another member's approval.

| Confirmation | Actual member(s) | Date / evidence | Status |
|---|---|---|---|
| Read the pinned requirements and local Week 1 scope | **PENDING** | **PENDING** | **PENDING** |
| Accepted role assignments | **PENDING** | **PENDING** | **PENDING** |
| Agreed on stack, embedding model, and vector store | **PENDING** | **PENDING** | **PENDING** |
| Reviewed and agreed on [6-pager](6-pager.md) | **PENDING — whole team** | **PENDING** | **PENDING** |
| Reviewed and agreed on [PR/FAQ](pr-faq.md) | **PENDING — whole team** | **PENDING** | **PENDING** |
| Fresh-clone run completed from README alone | **PENDING — teammate** | **PENDING** | **PENDING** |
| Verified UI screenshot/share link and posted it to the agreed team channel | **PENDING** | **PENDING** | **PENDING** |

Draft documents are ready for review when their contents are complete. The
upstream team-agreement conditions remain incomplete until these actual
confirmations are recorded.
