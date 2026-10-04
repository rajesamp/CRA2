# Team and stack record — draft

**Status: all confirmations PENDING.** This file records proposed assignments
and a proposed stack. Creating it does not show that any teammate read or
agreed to it.

Scope adapts task 1 from the pinned [upstream task plan](https://github.com/abhineer/Sep-Projects/blob/3e52f28ae1f430211d2df6098ab366f38ebdb86e/ChangeRiskAdvisor/tasks.md)
and [requirements](https://github.com/abhineer/Sep-Projects/blob/3e52f28ae1f430211d2df6098ab366f38ebdb86e/ChangeRiskAdvisor/requirements.md).
Only tasks 1–11 are in scope. The upstream persona is **Sameer**, also called
**Sam**; this project uses the established alias **Raj Sam** for the same
DevOps reviewer scenario. That is a documentation mapping, not a claim about
real teammates or customers. Existing code, prompts, and documents keep their
names.

## Proposed responsibilities

Role categories follow the upstream plan so later work has a home. One person
may cover several roles once the team confirms.

| Role | Current responsibility | Later work, out of scope | Member |
|---|---|---|---|
| Prompt and RAG | Advisory prompt, corpus design, ingestion, retrieval judgment, two manual transcripts | Broader retrieval evaluation | **PENDING** |
| Tools/MCP | Review the static graph and health fixtures; label them snapshots | Health/dependency tools, MCP integration | **PENDING** |
| Memory | Confirm the demo never claims to remember new preferences across visits | Persistent preference memory, two-session verification | **PENDING** |
| Guardrails/caching | Preserve current protections; check citations and the refusal to approve; review new data handling | Tool-aware guardrails, caching work | **PENDING** |
| Observability/UI | Local Gradio workflow, ingestion and run evidence, screenshot and share-link record | Tool tracing, operational dashboard | **PENDING** |
| Documentation coordination | Reconcile scope, coordinate narrative and PR/FAQ reviews, gather completion evidence | Planning after acceptance | **PENDING** |

No member names or attendance records were supplied. The product persona does
not fill missing ownership information.

## Proposed stack

The additive implementation lives in an isolated `week1/` uv project. These
selections describe the prototype and recorded local checks, not a completed
team agreement. Root dependencies and core CRA2 files are unchanged.

| Layer | Selection | Evidence | Agreement |
|---|---|---|---|
| Language and environment | Python 3.13 target; separate `week1/` uv project | [Manifest](../week1/pyproject.toml), [lockfile](../week1/uv.lock) | **PENDING** |
| Assessment baseline | Keep the CRA2 library, CLI, and advisory policies | Source, [architecture](architecture.md), offline tests | **PENDING** |
| Model provider | Optional Groq call selects citations and uncalibrated severity; the UI shows source excerpts and fixed review questions, not model prose. Local-evidence mode gives no model risk indication | [Chat](../week1/chat.py), [provider](../week1/provider.py), [demo evidence](evidence/week1-demo.md) | **PENDING** |
| Corpus | 11 new Markdown documents: 6 postmortems derived from synthetic CX incident facts, 5 runbooks; plus 46 incident records | [Manifest](../week1/corpus/manifest.json); 57 documents and 68 chunks measured in [retrieval evidence](evidence/week1-retrieval.md) | **PENDING** |
| Embeddings | FastEmbed 0.8.1, `BAAI/bge-small-en-v1.5`, local 384-dimensional vectors | 68 stored embeddings in [retrieval evidence](evidence/week1-retrieval.md) | **PENDING** |
| Vector storage | Local SQLite store, cosine similarity | [Retrieval](../week1/retrieval.py); judged top-three checkout probe in [retrieval evidence](evidence/week1-retrieval.md) | **PENDING** |
| UI | Gradio 6.28.0 local chat on port 7861; `--share` requires `CRA2_UI_USER` and `CRA2_UI_PASSWORD` | [App](../week1/app.py); screenshot tracked in [demo evidence](evidence/week1-demo.md), share link pending | **PENDING** |
| Verification | Offline regressions, measured ingestion, judged retrieval, bounded manual UI and provider checks | [Retrieval evidence](evidence/week1-retrieval.md), [demo evidence](evidence/week1-demo.md), [task alignment](evidence/week1-alignment.md); no risk-calibration claim | **PENDING** |
| Branch workflow | Feature branch with a reviewable pull request against this repository | Proposed workflow; not an attestation of a merge or team agreement | **PENDING** |

Two live model checks produced unsupported factual claims despite valid citation
IDs, so the UI displays authoritative cited passages plus fixed human-review
questions. Model severity and citation selection stay uncalibrated. These
technical checks establish neither semantic accuracy nor team acceptance.

New flows use static or explicitly simulated information. Existing CRA2
validation, credential safeguards, policy floors, and caching stay in place.
The upstream simplification is not a reason to remove them. No tools, MCP
integration, memory writes, live infrastructure checks, or deployment actions
are in scope.

The [README](../README.md) stays the fresh-clone entry point, and a teammate
must verify its additive instructions. No public share link or team-channel post
is recorded. Never commit sharing credentials or copy them into screenshots,
URLs, or transcripts.

## Confirmations

Replace a pending entry only after the named member provides the confirmation.
Record the date and a review or message reference. Do not infer agreement from a
file existing, a test passing, or another member approving.

| Confirmation | Member | Date / evidence | Status |
|---|---|---|---|
| Read the pinned requirements and local scope | **PENDING** | **PENDING** | **PENDING** |
| Accepted role assignments | **PENDING** | **PENDING** | **PENDING** |
| Agreed on stack, embedding model, and vector store | **PENDING** | **PENDING** | **PENDING** |
| Reviewed and agreed on [6-pager](6-pager.md) | **PENDING — whole team** | **PENDING** | **PENDING** |
| Reviewed and agreed on [PR/FAQ](pr-faq.md) | **PENDING — whole team** | **PENDING** | **PENDING** |
| Fresh-clone run completed from the README alone | **PENDING — teammate** | **PENDING** | **PENDING** |
| Verified UI screenshot and share link, posted to the agreed channel | **PENDING** | **PENDING** | **PENDING** |