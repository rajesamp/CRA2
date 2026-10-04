# CRA2 six-pager

**Draft for team review. Whole-team agreement is PENDING.** Measured retrieval
and UI/provider checks exist. Teammate acceptance, fresh-clone verification, and
public sharing do not.

Scope adapts tasks 1–11 of the pinned [upstream task plan](https://github.com/abhineer/Sep-Projects/blob/3e52f28ae1f430211d2df6098ab366f38ebdb86e/ChangeRiskAdvisor/tasks.md)
and [requirements](https://github.com/abhineer/Sep-Projects/blob/3e52f28ae1f430211d2df6098ab366f38ebdb86e/ChangeRiskAdvisor/requirements.md).
The upstream Sameer/Sam persona appears here as the established alias Raj Sam.
That bridge preserves the existing project; it identifies no customer or
teammate.

## 1. The problem: change context is scattered

A configuration edit is easy to describe and hard to judge. The reviewer needs
to know which behavior changes, which services feel a failure, what happened
during similar changes, and whether the rollback and monitoring plans cover those
failure modes. An incident summary may hold the lesson, a runbook the recovery
steps, and a catalog the service relationships. Reading only the change title
misses the connection between them.

The upstream scenario describes a DevOps engineer reviewing changes across
services they do not know deeply. That is the hypothesis, not a research
finding. Review duration, incident avoidance, and workload are unmeasured, so
this delivery shows that the assistant finds and explains relevant evidence. It
claims no time saving and no prevented outage.

CRA2 already provides a structured-input CLI, local rule scoring, an advisory
policy, and bounded retrieval over incident records. The additive demonstration
adds chat. Document ingestion, embedding, vector retrieval, and the cited answer
path live in an isolated `week1/` project.

Lexical selection alone does not prove the vector path works, and a CLI run does
not prove a browser interface is usable or shareable.

The failure to avoid is an authoritative answer detached from evidence. A bare
number does not help a reviewer judge risk. A citation to an irrelevant incident
misleads just as badly. The demonstration must keep retrieved material
inspectable and leave the decision with the human.

## 2. The customer: a reviewer who keeps the decision

Raj Sam represents the engineer who receives a proposed change, understands part
of the system, and needs help locating relevant history. A useful first
interaction is a concrete checkout configuration change: the affected behavior
plus any rollout, rollback, and monitoring plans. The assistant should state what
its sources support, explain the connection to this change, and ask for missing
detail when the request is too vague to assess.

The upstream checkout-config example serves two distinct purposes. Its short
wording is a retrieval probe: the system should locate relevant incident
passages in its first three results. It is not enough information to justify a
risk score. A complete assessment demonstration must supply a concrete
modification or show the assistant asking for it before scoring. Inventing a
timeout value or rollback plan would defeat grounded review.

The six upstream examples also cover similar incidents, a current freeze,
payment dependencies, remembered preferences, and approval. This delivery
demonstrates historical retrieval and advisory behavior, and explains the limits
of the rest. A dated fixture can be described as a snapshot; it cannot establish
current production state. A request to remember a preference must not receive a
false persistence confirmation. A request for approval must receive a clear
refusal plus an offer to assess the change.

This is a demonstration for team review. Demand, usability, and a real customer
workflow are unvalidated, and those gaps stay visible.

## 3. The solution: a small, inspectable retrieval workflow

The implementation is an isolated Python 3.13 uv project with Gradio 6.28.0
alongside the existing CLI and library. Its [app](../week1/app.py),
[chat adapter](../week1/chat.py), and [retrieval module](../week1/retrieval.py)
are additive; root dependencies and core code are unchanged.

The prototype takes a natural-language change description, retrieves local
passages, and optionally requests a cited assessment through the existing
protected Groq path. Local-evidence mode returns documents without a model risk
indication. Neither mode calls operational tools. Local checks are in
[demo evidence](evidence/week1-demo.md); team acceptance is pending.

The corpus holds eleven Markdown documents: six postmortems derived from
synthetic CX incident facts and five runbooks. With the 46 existing incident
records, the measured index holds 57 logical documents and 68 chunks.

Source identity survives ingestion. Every retrieved passage carries a document
reference and a stable chunk identifier so a reviewer can inspect the supporting
text. The eight-service synthetic catalog and its incidents provide a controlled
example system. Separately approved sanitized samples may supply analogies, but
their original service labels and provenance stay intact.

The embedding path is FastEmbed 0.8.1 with `BAAI/bge-small-en-v1.5`, producing
local 384-dimensional embeddings stored in SQLite and compared with cosine
similarity. [Retrieval evidence](evidence/week1-retrieval.md) records 68 stored
embeddings, the model fingerprint, and a fresh-process search with network
connections blocked. The top-three checkout probe carries coding-agent
relevance judgments; one query establishes no general retrieval quality. A
similarity value is not a risk score, and a repeated type label does not make a
useful analogy.

The model selects citations and uncalibrated severity. The display quotes
authoritative cited passages and adds fixed human-review questions. Free-form
model prose is not displayed, and insufficient evidence yields no risk
indication. The local Gradio UI runs on port 7861; final screenshot capture is
tracked in [demo evidence](evidence/week1-demo.md). Public sharing is a separate
pending item: `--share` requires `CRA2_UI_USER` and `CRA2_UI_PASSWORD`. No
public link or team-channel post is recorded here.

## 4. Goals and non-goals

Eleven explicit tasks remain: assign roles, read requirements, agree on a stack,
review this narrative and the mock PR/FAQ, prove a fresh-clone run, save two
manual prompt transcripts, document the synthetic dataset, prepare the corpus,
run chunking and embedding, judge checkout retrieval, demonstrate a
description-to-assessment round trip, and demonstrate the Gradio UI with its
sharing evidence. An artifact can exist while its review or runtime proof stays
pending, and the task record should distinguish those states.

Covering six example queries does not bring later tools or memory into scope.
Corpus material can explain the historical evidence and static scenario behind
those questions. The prototype must still state when it cannot confirm current
health, the current freeze calendar, or live dependency state. Static graph
answers must disclose their source and avoid claiming a live lookup. The
approval example is answered by the advisory rule; it is not permission to
create an approval action. The memory example stays an explicit limitation until
persistence is implemented and tested.

Existing CRA2 safeguards stay. Clarification behavior, review-only routes,
evidence checks, credential protections, and explicit uncertainty about
reported freezes constrain any new demonstration. The upstream sequence adds
guardrail work later, but removing working protections is unnecessary. The team
settings file is configuration; it does not prove conversational memory across
two visits.

This delivery proposes no MCP service, production integration, multiuser
identity system, persistent preference memory, observability dashboard, or
deployment automation. Finishing eleven tasks does not complete the four-week
product. Later scope needs a separate accepted increment.

## 5. Risks and mitigations

**Unsupported confidence.** Retrieval can match similar words while describing a
different failure mechanism. The demonstration must show source text, keep
original service names, separate same-service history from cross-service
analogy, and leave the connection to the reviewer. Cross-service history can
never become a same-service repeat penalty. Citation membership checks do not
establish that model interpretation is correct: two live checks showed this — one
embellished charges without orders as financial loss, another attributed
CX-102's retry storm to CX-101. Source-excerpt display keeps those claims out of
the answer but does not validate model-selected severity or relevance. The
failed attempts stay disclosed in [demo evidence](evidence/week1-demo.md).

**Overstated freshness or authority.** A simulated health field is not a current
check, and an active-freeze flag stays unconfirmed until verified. The interface
and prompt must describe the data as static and keep the freeze-verification
question visible. No route is an approval or a rejection. The two manual prompt
checks should include an approval request and an evidence-backed assessment, with
complete saved transcripts rather than rewritten examples of what the model was
expected to do.

**Data exposure.** Synthetic fixtures and approved sanitized samples have
different provenance and must stay distinguishable. Provider-assisted answers
may send the change and retrieved passages off the machine. Credentials do not
belong in changes, transcripts, screenshots, or corpus documents. Existing
exact-key protections stay enabled but do not detect every unknown or transformed
secret. A shareable demo must use agreed demonstration data, and its sharing
record must be captured only after the link works.

**Mistaking paperwork for completion.** Draft ownership is not an assignment,
model output is not customer validation, and a diagram is not an ingestion run.
Team confirmations stay pending until received. Current code and historical
evaluations remain useful baseline evidence, but new retrieval, chat, and UI
claims need their own runs.

## 6. Success measures and the decision to continue

Success means a reviewer can inspect a working, bounded demonstration and the
evidence behind it. The [ingestion and retrieval record](evidence/week1-retrieval.md)
holds actual totals, matching store count, and the judged checkout probe.
[Demo evidence](evidence/week1-demo.md) records the local round trip and its
limits. [Task alignment](evidence/week1-alignment.md) separates technical
completion from pending human acceptance. Missing evidence stays a visible
limitation rather than a model-generated explanation.

Prompt evidence must contain two actual manual runs: the advisory boundary and a
source-backed assessment. UI evidence must contain a screenshot of the running
app and a verified shareable link. The upstream task also requires a
team-channel post, which stays pending until the destination and authorization
exist and an actual post is recorded. Creating these documents sends no
announcement or message.

Coordination evidence is equally specific. A teammate should run the project
from a fresh clone using the README alone and record the outcome. The team
should confirm role assignments and stack choices, then record that all members
reviewed this memo and the PR/FAQ. These are acceptance requirements, not
completed activities. Any unresolved selection, review, or runtime proof stays
marked pending.

No claim here covers production accuracy, latency improvement, cost savings,
adoption, or prevented incidents. Existing calibration reports establish none of
those for a retrieval workflow. The end-of-week decision is whether the team
demonstrated useful retrieval and an understandable advisory interaction with
reproducible evidence. Only then should it plan the next increment — operational
tools or persistent memory — with its own scope and acceptance criteria.