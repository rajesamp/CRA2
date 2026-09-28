# CRA2 Week 1 mock press release and FAQ

**Draft for team review — not a launch announcement.** Whole-team review and
agreement are **PENDING**. A local prototype and measured retrieval evidence
exist; this mock release does not announce public availability, customer adoption,
or a team-channel post. Fresh-clone and team acceptance remain pending. There are
no invented customer quotes or testimonials.

This original draft adapts Week 1 task 3 from the pinned [upstream task plan](https://github.com/abhineer/Sep-Projects/blob/3e52f28ae1f430211d2df6098ab366f38ebdb86e/ChangeRiskAdvisor/tasks.md)
and [requirements](https://github.com/abhineer/Sep-Projects/blob/3e52f28ae1f430211d2df6098ab366f38ebdb86e/ChangeRiskAdvisor/requirements.md).
The upstream Sameer/Sam scenario uses the existing CRA2 persona alias **Raj Sam**
here. Existing documents and code are not renamed.

## Mock press release

### CRA2 proposes a cited change review before the human decision

**A Week 1 demonstration would help engineers connect a proposed change to
documented failure modes, while keeping approval with their team.**

For Raj Sam, the difficult part of reviewing a change is often finding the
relevant context. A small checkout configuration adjustment may resemble an
earlier outage, while the useful rollback guidance lives in a different
document. The proposed CRA2 demonstration would let Raj describe the concrete
change in a Gradio chat and inspect an advisory assessment alongside the
incident or runbook passages supporting it.

The first version would use a local, documented corpus and static demonstration
data. It would retrieve relevant chunks from incident summaries, postmortems,
and runbooks, then display cited source excerpts with fixed review questions. It
would ask for more detail when the change is unclear and say when the available evidence
is insufficient. It would not fill those gaps with invented incidents or claim
that a snapshot represents the current production environment.

The proposed benefit is a more inspectable review conversation: Raj can read
the cited passage, decide whether an analogy applies, and take the question
back to the change owner. This benefit remains a hypothesis for the demo.
There is no measured promise of faster reviews, fewer outages, or cost savings.

CRA2 would never approve, reject, block, merge, or deploy a change. Its review
routes communicate the attention an assessment warrants, and the human team
retains the decision. Current health checks, live freeze-calendar queries,
tool-based dependency lookups, and preference memory across visits are outside
this Week 1 proposal.

The local prototype has measured ingestion and judged retrieval results in
[retrieval evidence](evidence/week1-retrieval.md); local UI and provider checks are
recorded in [demo evidence](evidence/week1-demo.md). A fresh-clone run, final UI
capture, public sharing, and team confirmations are separate acceptance items
tracked in [task alignment](evidence/week1-alignment.md) and [team.md](team.md).

## Customer questions

### 1. What would I enter, and what would I get back?

The [chat](../week1/chat.py) accepts a concrete change description with an exact
catalog service and intended behavior. Optional Groq assessment selects citations
and an uncalibrated risk indication. The display uses the cited source passages
and fixed human-review questions; it does not publish free-form model prose.
Vague requests receive clarification. Local-evidence mode returns documents
without a model risk indication. These checks do not establish predictive
accuracy or calibrated risk.

### 2. Can CRA2 approve the change for me?

No. It cannot approve, reject, block, merge, or deploy a change. The existing
`routine-review`, `focused-review`, and `priority-review` routes describe review
attention, not a go/no-go decision. An approval request should be declined with
a brief explanation and an offer to help assess the change. Week 1 requires a
saved manual transcript of that behavior, not an invented example presented as
a test result.

### 3. Can I trust its answer about a freeze or a dependency?

Week 1 uses static or explicitly simulated information. A graph passage can
describe the supplied snapshot; it cannot prove the current production graph.
A reported freeze stays unconfirmed and requires independent verification.
The prototype must disclose that limitation instead of saying it checked a live
system. Later operational tools are separate work. Even for historical evidence,
two live checks produced factual errors despite valid citation IDs: an invented
financial-loss consequence and a retry-storm claim attributed to the wrong
incident. The final display therefore excludes model prose and presents source
excerpts. Citation selection and severity can still be wrong; inspect the passage
and judge its relevance. See [demo evidence](evidence/week1-demo.md).

### 4. Will it remember that my service is always high-risk?

Conversational preference persistence is outside Week 1. The prototype must not
claim it saved a new preference for a future visit. Existing CRA2 team settings
can configure a service's risk treatment, but a static settings file is not proof
of memory across sessions. The upstream two-visit memory demonstration belongs
to a later increment. Week 1 should clearly explain this boundary when the
remember-preference example is used.

## Internal and guardrail questions

### 5. What data will the corpus and model use?

The additive corpus contains six postmortem documents derived from synthetic
CX incident facts and five runbooks, alongside the 46 existing incident records:
57 logical source documents. [Measured ingestion](evidence/week1-retrieval.md)
stored 68 chunks and 68 embeddings, each with 384 dimensions. CRA2 distinguishes
16 original synthetic incidents from 30 user-provided sanitized samples; their
approval for repository distribution and Groq context is not a general permission
to add arbitrary internal documents. New corpus documents need source identity,
and derived summaries must remain labeled as such. Provider-assisted answers may
send the change and retrieved passages to Groq. Credentials and confidential
unsanitized data do not belong in demonstration prompts or evidence artifacts.

### 6. What must exist before we mark the RAG work complete?

The implementation selects an isolated Python 3.13 uv project, FastEmbed 0.8.1,
the `BAAI/bge-small-en-v1.5` model's local 384-dimensional embeddings, and SQLite
storage with cosine similarity. Team agreement is pending. The
[retrieval record](evidence/week1-retrieval.md) verifies the stored count, local
model fingerprint, offline search, and the top three checkout results with
coding-agent relevance judgments. This is one judged query, not a general retrieval-quality
result or independent domain review. Corpus coverage should map all six upstream query categories to documents or explicit Week 1
limitations. Existing lexical retrieval, a list of source filenames, or a
generated answer without inspected sources does not complete these tasks.

### 7. What proof is needed for the UI and sharing task?

The [app](../week1/app.py) uses Gradio 6.28.0 in the separate Week 1 project;
root dependencies and core CRA2 files are unchanged. The local UI runs on port
7861; [demo evidence](evidence/week1-demo.md) tracks the actual runs and final
screenshot capture. Public-link verification remains pending. The upstream task
also calls for posting that link to the team channel; the destination,
authorization, and actual posting record remain pending. A
local CLI result or a mock screenshot is not UI evidence. This draft does not
publish a site, start a public tunnel, or send a message. Public sharing is an
explicit `--share` action requiring `CRA2_UI_USER` and `CRA2_UI_PASSWORD`.
No public link or team post is recorded here; never place those credentials in
the repository, screenshots, or evidence transcripts.

### 8. Why retain existing safeguards if the upstream plan adds them later?

Week 1 limits new scope; it does not require removing protections that CRA2
already has. Preserve advisory routing, validation, clarification, evidence
checks, credential protections, and explicit freeze uncertainty. New RAG and UI
components should reuse appropriate protections and be checked with actual
manual examples. Additional tools/MCP, persistent memory, tool observability,
new guardrail layers, and later-week caching work are not completion claims for
this delivery. Whole-team agreement on this boundary and the proposed stack is
still pending.
