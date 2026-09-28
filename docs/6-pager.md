# CRA2 Week 1: evidence-backed change review

**Narrative draft for team review.** Whole-team reading and agreement are
**PENDING**. The local prototype now has measured retrieval and UI/provider
checks. This memo distinguishes that technical evidence from unfinished teammate
acceptance, fresh-clone verification, and public sharing.

The scope is adapted from tasks 1–11 of the pinned [upstream task plan](https://github.com/abhineer/Sep-Projects/blob/3e52f28ae1f430211d2df6098ab366f38ebdb86e/ChangeRiskAdvisor/tasks.md)
and its [requirements](https://github.com/abhineer/Sep-Projects/blob/3e52f28ae1f430211d2df6098ab366f38ebdb86e/ChangeRiskAdvisor/requirements.md).
The upstream Sameer/Sam persona is represented here by CRA2's established alias,
Raj Sam. This naming bridge preserves the existing project; it does not identify
an actual customer or teammate.

## 1. The problem: change context is scattered

A proposed configuration edit can be easy to describe and difficult to judge.
The reviewer needs to understand which behavior will change, which services
could feel a failure, what happened during similar changes, and whether the
rollback and observation plans address those failure modes. An incident summary
may contain the relevant lesson, while a runbook contains the recovery steps
and a catalog contains the service relationships. Reading only the change title
can miss the connection between those sources.

The upstream scenario describes a DevOps engineer reviewing changes across
services they do not all know deeply. That is the problem hypothesis for this
prototype, not the result of customer interviews. We have not measured the
team's review duration, incident avoidance, or workload. Week 1 should therefore
show that the assistant can find and explain relevant evidence, rather than
claim that it saves a particular amount of time or prevents outages.

CRA2 already provides a useful starting point: a structured-input CLI, local
rule scoring, an advisory policy, and bounded retrieval over incident records.
The additive demonstration lets a reviewer use chat. Document ingestion,
embedding, vector retrieval, and a cited answer path live in an isolated `week1/`
project.
The existing lexical selection is not a substitute for evidence that the new
vector path works. Nor does a CLI invocation prove that a browser interface is
usable or shareable.

The central failure to avoid is an authoritative answer detached from evidence.
A number alone does not help the reviewer understand the risk. A citation to an
irrelevant incident can be equally misleading. The demonstration must make the
retrieved material inspectable and leave the actual decision with the human.

## 2. The customer: a reviewer who retains the decision

Raj Sam represents the engineer who receives a proposed change, understands
parts of the system, and needs help locating relevant history. A useful first
interaction is a concrete description of a checkout configuration change,
including the affected behavior and any known rollout, rollback, and monitoring
plans. The assistant should identify what its sources support, explain the
connection to this change, and ask for missing information when the request is
too vague to assess.

The upstream checkout-config example serves two purposes that should remain
distinct. Its short wording is a retrieval probe: the system should locate
relevant incident passages among its first three results. It is not necessarily
enough information to justify a risk score. A complete assessment demonstration
must supply a concrete modification, or show the assistant asking for that
detail before it scores anything. Filling in an imaginary timeout value or
rollback plan would defeat the purpose of grounded review.

The six upstream examples also ask about similar incidents, a current freeze,
payment dependencies, remembered team preferences, and approval. Week 1 can
demonstrate historical retrieval and advisory behavior, while explaining the
limits of the other examples. A dated static health or dependency fixture can
be described as a snapshot. It cannot establish current production state. A
request to remember a new preference should not receive a false persistence
confirmation. A request for approval must receive a clear refusal and an offer
to help assess the change instead.

This experience is intended for a demonstration and team review. We have not
validated demand, measured usability, or observed a real customer's workflow.
Those gaps should remain visible in the narrative and mock press release.

## 3. The solution: a small, inspectable retrieval workflow

The Week 1 implementation path is an isolated Python 3.13 uv project with
Gradio 6.28.0, alongside the existing CLI and library. Its [app](../week1/app.py),
[chat adapter](../week1/chat.py), and [retrieval module](../week1/retrieval.py)
are additive; root dependencies and core code remain unchanged. The
prototype accepts a natural-language change description, retrieves local
passages, and optionally requests a cited assessment through the existing
protected Groq request path. Local-evidence mode returns documents without a
model risk indication. Neither mode calls operational tools. Local checks are
recorded in [demo evidence](evidence/week1-demo.md); team acceptance is pending.

The new corpus contains eleven Markdown documents: six postmortems derived from
synthetic CX incident facts and five runbooks. Together with the 46 existing
incident records, the measured index contains 57 logical documents and 68 chunks.
Source identity survives ingestion. Each retrieved
passage needs a document reference and a stable chunk identifier so a reviewer
can inspect the supporting text. The eight-service synthetic catalog and the
original synthetic incidents provide a controlled example system. The separately
approved sanitized samples may supply analogies, but their original service
labels and provenance must remain intact.

The selected embedding path is FastEmbed 0.8.1 with `BAAI/bge-small-en-v1.5`,
producing local 384-dimensional embeddings stored in SQLite and compared using
cosine similarity. [Retrieval evidence](evidence/week1-retrieval.md) records 68
stored embeddings, their model fingerprint, and a fresh-process search with
network connections blocked. The top-three checkout probe has explicit
coding-agent relevance judgments; one query does not establish general retrieval
quality. Team agreement remains pending. A similarity value is not a risk score,
and repeating a type label does not establish a useful analogy.

The model selects citations and uncalibrated severity; the display quotes
authoritative cited passages and adds fixed human-review questions. Free-form
model prose is not displayed. Insufficient evidence yields no risk indication.
The local Gradio UI runs on port 7861; final screenshot capture is tracked in
[demo evidence](evidence/week1-demo.md). Public sharing remains a separate pending
item: `--share` requires `CRA2_UI_USER` and `CRA2_UI_PASSWORD`. No public link or
team-channel post is recorded here.

## 4. Goals and non-goals: finish Week 1 without implying later weeks

Week 1 has eleven explicit tasks. The team must assign roles, read the
requirements, and agree on a stack; review this narrative and the mock PR/FAQ;
prove a fresh-clone run; save two manual prompt transcripts; document the
synthetic dataset; prepare the corpus; run chunking and embedding; judge the
checkout retrieval results; demonstrate a complete description-to-assessment
round trip; and demonstrate the Gradio UI with its required sharing evidence.
An artifact can exist while its team review or runtime proof remains pending.
The task record should distinguish those states.

The corpus requirement to cover six example queries does not bring later-week
tools or memory into scope. Corpus material can explain the historical evidence
and static scenario behind those questions. The prototype must still state
when it cannot confirm current health, the current freeze calendar, or live
dependency state. Static graph answers should disclose their source and avoid
claiming a live lookup. The approval example is answered by the advisory rule;
it is not permission to create an approval action. The memory example remains
an explicit limitation until persistence is implemented and tested separately.

Existing CRA2 safeguards are retained. Its clarification behavior, review-only
routes, evidence checks, credential protections, and explicit uncertainty about
reported freezes are useful constraints on any new demonstration. The upstream
sequence places additional guardrail work in later weeks, but removing working
protections is not necessary to keep Week 1 small. Likewise, the existing team
settings file is configuration; it does not prove conversational memory across
two visits.

No new MCP service, production integration, multiuser identity system, persistent
preference memory, observability dashboard, or deployment automation is proposed
for this delivery. We do not claim to complete the full four-week product by
finishing the first eleven tasks. Any later scope should be proposed and accepted
as a separate increment after the Week 1 evidence is reviewed.

## 5. Risks and mitigations: protect the meaning of the evidence

The first risk is unsupported confidence. Retrieval may find a passage with
similar words that describes a different failure mechanism. The prototype should
show source text, retain original service names, distinguish same-service history
from cross-service analogies, and make the reviewer judge the connection. The
existing rule that cross-service history cannot become a same-service repeat
penalty remains relevant. Citation membership checks do not establish that the
model's interpretation is correct. Two live checks demonstrated this failure:
one embellished charges without orders as financial loss; another attributed
CX-102's retry storm to CX-101. The final source-excerpt display prevents those
free-form claims from reaching the answer, but does not validate model-selected
severity or relevance. The failed attempts remain disclosed in
[demo evidence](evidence/week1-demo.md).

The second risk is overstating freshness or authority. A simulated service
health field is not a current check, and an active-freeze flag remains unconfirmed
until independently verified. The interface and prompt should describe the data
as static and keep any freeze-verification question visible. None of the review
routes is an approval or rejection. The two manual prompt checks should include
an approval request and an evidence-backed assessment, with complete saved
transcripts rather than rewritten examples of what the model was expected to do.

The third risk concerns data exposure. Synthetic fixtures and the approved
sanitized samples have different provenance and must remain distinguishable.
Provider-assisted answers may send the change and retrieved passages off the
machine. Credentials do not belong in changes, transcripts, screenshots, or
corpus documents. Existing exact-key protections should stay enabled, but they
do not detect every unknown or transformed secret. A shareable demo should use
the agreed demonstration data, and its actual sharing record must be captured
only after the link works.

The final risk is mistaking paperwork for completion. Draft ownership is not an
assignment, model output is not customer validation, and a diagram is not an
ingestion run. The team record should leave member confirmations pending until
they are received. Current code and historical evaluations remain useful
baseline evidence, but new retrieval, chat, and UI claims need their own runs.

## 6. Success measures and the decision to continue

Success in Week 1 means a reviewer can inspect a working, bounded demonstration
and the evidence behind it. The [ingestion and retrieval record](evidence/week1-retrieval.md)
contains the actual totals, matching store count, and judged checkout probe.
[Demo evidence](evidence/week1-demo.md) records the local change-description
round trip and its limits; [task alignment](evidence/week1-alignment.md) separates
technical completion from pending human acceptance. Missing evidence should
remain a visible limitation rather than a model-generated explanation.

The prompt evidence must contain two actual manual runs demonstrating the
advisory boundary and source-backed assessment. The UI evidence must contain
an actual running-app screenshot and a verified shareable link. The upstream
task also requires a team-channel post; that remains pending until the posting
destination and authorization are established and an actual post is recorded.
No announcement or message is made by creating these documents.

The coordination evidence is equally specific. A teammate should run the project
from a fresh clone using the README alone and record the command outcome. The
team should confirm its role assignments and stack choices, then record that
all members reviewed this memo and the PR/FAQ. These are acceptance requirements,
not completed activities. Any unresolved selection, review, or runtime proof
should stay marked pending in the Week 1 record.

There is no measured claim here about production accuracy, latency improvement,
cost savings, adoption, or prevented incidents. Existing calibration reports do
not establish those outcomes for a new RAG workflow. The decision at the end of
Week 1 is whether the team has demonstrated useful retrieval and an understandable
advisory interaction with reproducible evidence. Only then should it plan the
next increment, including operational tools or persistent memory, with its own
scope and acceptance criteria.
