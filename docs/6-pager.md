# CRA2 Week 1: evidence-backed change review

**Narrative draft for team review.** Whole-team reading and agreement are
**PENDING**. Engineering for Week 1 closed on 2026-09-30 (see section 6);
teammate acceptance, a fresh-clone run, and public sharing remain open.

The scope is adapted from tasks 1–11 of the pinned [upstream task plan](https://github.com/abhineer/Sep-Projects/blob/3e52f28ae1f430211d2df6098ab366f38ebdb86e/ChangeRiskAdvisor/tasks.md)
and its [requirements](https://github.com/abhineer/Sep-Projects/blob/3e52f28ae1f430211d2df6098ab366f38ebdb86e/ChangeRiskAdvisor/requirements.md).
The upstream Sameer/Sam persona is represented by CRA2's existing alias, Raj Sam.

## 1. The problem: change context is scattered

Raj is asked to review a one-line change: lower the payment-call timeout in
`checkout-service` from 4 seconds to 400 milliseconds. The edit is trivial to
read and hard to judge. Raj needs to know which behavior changes, which
services feel a failure, what happened the last time something like this
shipped, and whether the rollback and monitoring plans match the failure. The
lesson sits in an incident record, the recovery steps in a runbook, and the
service relationships in a catalog. Reading the change title connects none of
them.

In the synthetic history this is exactly CX-101: a payment-call timeout cut from
4 seconds to 400 milliseconds led to abandoned authorisations and charges
without orders. A reviewer who knows that incident asks the right questions at
once. A reviewer who does not may approve on the strength of a small diff.

The problem hypothesis comes from the upstream scenario, a DevOps engineer
reviewing changes across services they do not all know deeply. It is not the
result of customer interviews. We have not measured review time, incident
avoidance, or workload, so Week 1 aims to show that the assistant finds and
explains relevant evidence. It makes no claim about time saved or outages
prevented.

The failure to avoid is an authoritative answer detached from evidence. A bare
risk number does not help Raj, and a citation to an irrelevant incident is
worse. The demonstration must make retrieved material inspectable and leave the
decision with the human.

## 2. The customer: a reviewer who keeps the decision

Raj Sam represents an engineer who receives a proposed change, understands part
of the system, and needs help locating relevant history. A good first
interaction is a concrete description of a checkout configuration change with
the affected behavior and any known rollout, rollback, and monitoring plans. The
assistant should say what its sources support, explain how they connect to this
change, and ask for missing detail when the request is too vague to assess.

An illustrative exchange (written for this memo, not a saved run; saved runs are
in [demo evidence](evidence/week1-demo.md)): Raj describes the 400 ms timeout
change. The assistant returns the CX-101 postmortem and the checkout config
runbook as cited excerpts, followed by fixed review questions: what happens when
a request times out after the external payment operation has started, can
cancellation, retry, and order creation leave payment and order state
inconsistent, and how would monitoring show charges without completed orders.
Raj decides.

Two upstream behaviors must stay distinct. The short checkout-config query is a
retrieval probe: relevant passages should appear in the top three results. It
does not carry enough detail to justify a risk score. A full assessment needs a
concrete modification, or the assistant must ask for one before scoring.
Inventing a timeout value or rollback plan would defeat grounded review.

The other upstream examples ask about similar incidents, a current freeze,
payment dependencies, remembered preferences, and approval. Week 1 covers
historical retrieval and advisory behavior and explains the limits of the rest.
A dated health or dependency fixture is a snapshot, not current production
state. A request to remember a preference gets no false persistence
confirmation. A request for approval gets a clear refusal and an offer to
assess the change instead.

We have not validated demand, measured usability, or observed a real
customer's workflow. Those gaps stay visible here and in the
[PR/FAQ](pr-faq.md).

## 3. The solution: a small, inspectable retrieval workflow

The Week 1 path is an isolated Python 3.13 uv project with Gradio 6.28.0,
alongside the existing CLI and library. The [app](../week1/app.py),
[chat adapter](../week1/chat.py), and [retrieval module](../week1/retrieval.py)
are additive; root dependencies and core code are unchanged. The prototype
takes a natural-language change description, retrieves local passages, and
optionally requests a cited assessment through the existing protected Groq
request path. Local-evidence mode returns documents with no model risk
indication. Neither mode calls operational tools.

The corpus has eleven Markdown documents: six postmortems derived from
synthetic CX incident facts and five runbooks. With the 46 existing incident
records, the measured index holds 57 logical documents and 68 chunks. Each
retrieved passage carries a document reference and stable chunk identifier so
Raj can inspect the supporting text. The eight-service synthetic catalog and
the original incidents form a controlled example system. The approved sanitized
samples may supply analogies, but keep their original service labels and
provenance.

Embeddings use FastEmbed 0.8.1 with `BAAI/bge-small-en-v1.5`: local
384-dimensional vectors in SQLite, compared by cosine similarity.
[Retrieval evidence](evidence/week1-retrieval.md) records the 68 stored
embeddings, the model fingerprint, and a fresh-process search with network
connections blocked. A similarity score is not a risk score, and a shared type
label does not make a useful analogy.

The model selects citations and an uncalibrated severity. The display quotes the
cited passages and adds fixed human-review questions; free-form model prose is
not shown. Insufficient evidence yields no risk indication. A local router
handles dataset questions and out-of-scope requests before retrieval or any
provider call. The local UI listens on port 7860, or 7861 with `--port 7861`.
Public sharing is a separate pending item: `--share` requires `CRA2_UI_USER` and
`CRA2_UI_PASSWORD`, and no public link or team-channel post is recorded.

## 4. Goals and non-goals

Week 1 has eleven tasks: assign roles, read the requirements, and agree on a
stack; review this memo and the PR/FAQ; prove a fresh-clone run; save two manual
prompt transcripts; document the synthetic dataset; prepare the corpus; run
chunking and embedding; judge the checkout retrieval results; demonstrate a
description-to-assessment round trip; and demonstrate the Gradio UI with
sharing evidence. An artifact can exist while its review or runtime proof is
still pending, and the task record keeps those states apart.

Covering six example queries in the corpus does not bring later-week tools or
memory into scope. The prototype must say when it cannot confirm current health,
the freeze calendar, or live dependency state, and static graph answers must
name their source rather than imply a live lookup. Approval is answered by the
advisory rule, not by an approval action. Memory stays an explicit limitation
until persistence is built and tested separately.

Existing CRA2 safeguards stay: clarification for vague requests, review-only
routes, evidence checks, credential protections, and an unconfirmed freeze with
its verification question. The team settings file is configuration, not
conversational memory.

Out of scope: a new MCP service, production integration, multiuser identity,
persistent preference memory, an observability dashboard, and deployment
automation. Finishing the first eleven tasks does not complete the four-week
product. Later scope is a separate increment, proposed after this evidence is
reviewed.

## 5. Risks and mitigations

**Unsupported confidence.** Retrieval can return a passage with similar words
and a different failure mechanism. The prototype shows source text, keeps
original service names, separates same-service history from cross-service
analogies, and asks Raj to judge the connection. Cross-service history never
becomes a same-service repeat penalty. Citation membership checks do not prove
the model interpreted a passage correctly: two live checks showed this, one
embellishing charges without orders as financial loss and one attributing CX-102's
retry storm to CX-101. The source-excerpt display keeps those free-form claims
out of the answer, but it does not validate model-selected severity or
relevance. The failed attempts are disclosed in [demo evidence](evidence/week1-demo.md).

**Overstated freshness or authority.** A simulated health field is not a current
check, and an active-freeze flag stays unconfirmed until independently verified.
The interface and prompt describe the data as static and keep the freeze
question visible. No route is an approval or rejection.

**Data exposure.** Synthetic fixtures and the approved sanitized samples have
different provenance and stay distinguishable. Provider-assisted answers may
send the change and retrieved passages off the machine. Credentials do not
belong in changes, transcripts, screenshots, or corpus documents. Exact-key
protections remain on, though they cannot detect every unknown or transformed
secret. A shared demo should use the agreed demonstration data.

**Paperwork mistaken for completion.** A draft owner is not an assignment, model
output is not customer validation, and a diagram is not an ingestion run. Member
confirmations stay pending until received, and new retrieval, chat, and UI
claims need their own runs.

## 6. Success measures and the decision to continue

**Status at close-out, 2026-09-30.** The owner closed Week 1 engineering after
the routing fixes. [Close-out evidence](evidence/week1-routing-closeout.md)
records 402 core and 262 Week 1 offline tests passing and the fast evaluation at
100/100 assessments over 20 cases and five repeats, with zero provider attempts.
A later scope fix raised the Week 1 count to 449 passing
([scope evidence](evidence/week1-question-scope.md)). These show the code behaves
as specified, not that the retrieval is good in general.

**Criteria for continuing.** Week 1 succeeds if all of the following hold:

1. The checkout probe returns checkout incident or postmortem context in the top
   three results. This is met for one query ([retrieval evidence](evidence/week1-retrieval.md)).
   Before planning Week 2, extend the judged set to at least five distinct
   queries, with relevant context in the top three for at least four.
2. A detailed change description produces a cited assessment, and a vague one
   produces a clarification with no score. Both are recorded in
   [demo evidence](evidence/week1-demo.md).
3. Two saved manual prompt runs show the advisory boundary (an approval request
   refused) and a source-backed assessment.
4. A teammate runs the project from a fresh clone using the README alone and
   records the outcome.
5. Teammates record that they reviewed this memo and the PR/FAQ, and the role
   and stack choices are confirmed.
6. A running-app screenshot exists. A verified share link and team-channel post
   follow once the destination and authorization are set.

Items 1 (extended set), 4, 5, and the share link are the open ones. If the
extended retrieval set falls below four of five, fix retrieval or the corpus
before adding tools or memory.

There is no measured claim here about production accuracy, latency, cost
savings, adoption, or prevented incidents. The decision at the end of Week 1 is
whether the team has shown useful retrieval and an understandable advisory
interaction with reproducible evidence. Only then should it plan the next
increment, including operational tools or persistent memory, with its own scope
and acceptance criteria.
