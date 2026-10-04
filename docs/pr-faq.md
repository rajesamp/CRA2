# CRA2 mock press release and FAQ

**Draft for team review, not a launch announcement. Whole-team agreement is
PENDING.** A local prototype and measured retrieval evidence exist. This mock
release announces no public availability, no customer adoption, and no
team-channel post. Fresh-clone and team acceptance remain pending. It contains
no invented customer quotes.

The draft adapts task 3 from the pinned [upstream task plan](https://github.com/abhineer/Sep-Projects/blob/3e52f28ae1f430211d2df6098ab366f38ebdb86e/ChangeRiskAdvisor/tasks.md)
and [requirements](https://github.com/abhineer/Sep-Projects/blob/3e52f28ae1f430211d2df6098ab366f38ebdb86e/ChangeRiskAdvisor/requirements.md).
The upstream Sameer/Sam scenario uses the existing alias **Raj Sam**. Existing
documents and code are not renamed.

## Mock press release

### CRA2 proposes a cited change review before the human decision

**A demonstration would help engineers connect a proposed change to documented
failure modes while keeping approval with their team.**

For Raj Sam, the hard part of reviewing a change is often finding relevant
context. A small checkout configuration adjustment may resemble an earlier
outage, while the useful rollback guidance lives in a different document. The
demonstration would let Raj describe the concrete change in a Gradio chat and
inspect an advisory assessment beside the incident or runbook passages
supporting it.

The first version uses a local documented corpus and static demonstration data.
It retrieves relevant chunks from incident summaries, postmortems, and runbooks,
then displays cited source excerpts with fixed review questions. It asks for
more detail when the change is unclear and says when the evidence is
insufficient. It does not fill gaps with invented incidents, and it does not
present a snapshot as the current production environment.

The proposed benefit is a more inspectable review conversation: Raj reads the
cited passage, decides whether an analogy applies, and takes the question back
to the change owner. That benefit is a hypothesis for the demo. There is no
measured promise of faster reviews, fewer outages, or cost savings.

CRA2 never approves, rejects, blocks, merges, or deploys a change. Its review
routes communicate the attention an assessment warrants, and the human team
keeps the decision. Current health checks, live freeze-calendar queries,
tool-based dependency lookups, and preference memory across visits are outside
this proposal.

Measured ingestion and judged retrieval results are in
[retrieval evidence](evidence/week1-retrieval.md); local UI and provider checks
are in [demo evidence](evidence/week1-demo.md). Fresh-clone run, final UI
capture, public sharing, and team confirmations are separate acceptance items,
tracked in [task alignment](evidence/week1-alignment.md) and [team.md](team.md).

## Customer questions

### What do I enter, and what do I get back?

The [chat](../week1/chat.py) takes a concrete change description with an exact
catalog service and intended behavior. Optional Groq assessment selects
citations and an uncalibrated risk indication. The display uses cited source
passages and fixed human-review questions; it does not publish free-form model
prose. Vague requests receive clarification. Local-evidence mode returns
documents without a model risk indication. None of this establishes predictive
accuracy or calibrated risk.

### Can CRA2 approve the change for me?

No. It cannot approve, reject, block, merge, or deploy. The routes
`routine-review`, `focused-review`, and `priority-review` describe review
attention, not a go/no-go decision. An approval request should be declined
briefly, with an offer to help assess the change instead. This behavior needs a
saved manual transcript, not an invented example presented as a test result.

### Can I trust its answer about a freeze or a dependency?

This demo uses static or explicitly simulated information. A graph passage can
describe the supplied snapshot; it cannot prove the current production graph. A
reported freeze stays unconfirmed and needs independent verification. The
prototype must disclose that limit rather than claim a live system check, and
operational tools are separate later work.

Historical evidence is not automatically safe either: two live checks produced
factual errors despite valid citation IDs — an invented financial-loss
consequence, and a retry-storm claim attributed to the wrong incident. The
display therefore excludes model prose and presents source excerpts. Citation
selection and severity can still be wrong. Inspect the passage and judge its
relevance. See [demo evidence](evidence/week1-demo.md).

### Will it remember that my service is always high-risk?

No. Preference persistence is out of scope. The prototype must not claim it
saved a new preference for a future visit. Existing CRA2 team settings can
configure a service's risk treatment, but a static settings file proves no
memory across sessions. This boundary should be stated plainly whenever the
remember-preference example is used.

## Internal questions

### What data do the corpus and model use?

The additive corpus holds six postmortems derived from synthetic CX incident
facts and five runbooks, alongside 46 existing incident records: 57 logical
source documents. [Measured ingestion](evidence/week1-retrieval.md) stored 68
chunks and 68 embeddings at 384 dimensions.

CRA2 distinguishes 16 original synthetic incidents from 30 user-provided
sanitized samples. Approval for repository distribution and Groq context is not
a general permission to add arbitrary internal documents. New corpus documents
need source identity, and derived summaries stay labeled as derived.
Provider-assisted answers may send the change and retrieved passages to Groq.
Credentials and unsanitized confidential data do not belong in demonstration
prompts or evidence artifacts.

### What must exist before the retrieval work is complete?

The implementation selects an isolated Python 3.13 uv project, FastEmbed 0.8.1,
local 384-dimensional `BAAI/bge-small-en-v1.5` embeddings, and SQLite storage
with cosine similarity. Team agreement is pending.

The [retrieval record](evidence/week1-retrieval.md) verifies the stored count,
the local model fingerprint, an offline search, and the top three checkout
results with coding-agent relevance judgments. That is one judged query, not a
general retrieval-quality result or an independent domain review. Corpus
coverage must map all six upstream query categories to documents or to explicit
stated limits. Existing lexical retrieval, a list of filenames, or a generated
answer without inspected sources does not complete these tasks.

### What proof does the UI and sharing task need?

The [app](../week1/app.py) uses Gradio 6.28.0 in the separate project; root
dependencies and core CRA2 files are unchanged. The local UI runs on port 7861,
and [demo evidence](evidence/week1-demo.md) tracks actual runs and final
screenshot capture. Public-link verification is pending.

The upstream task also requires posting that link to the team channel. The
destination, authorization, and actual posting record are all pending. A stored
transcript or a mock screenshot is not UI evidence. This draft publishes no
site, starts no public tunnel, and sends no message. Public sharing is an
explicit `--share` action requiring `CRA2_UI_USER` and `CRA2_UI_PASSWORD`; never
place those credentials in the repository, screenshots, or evidence transcripts.

### Why keep existing safeguards if the upstream plan adds them later?

Limiting scope does not require removing protections CRA2 already has. Preserve
advisory routing, validation, clarification, evidence checks, credential
protections, and explicit freeze uncertainty. New retrieval and UI components
should reuse those protections and be checked with actual manual examples.

Tools/MCP, persistent memory, tool observability, new guardrail layers, and
later caching work are not completion claims for this delivery. Whole-team
agreement on this boundary and the proposed stack is still pending.