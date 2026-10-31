# Intent: CRA2 Weeks 3–4

Status: planning draft, prepared at the owner's request on 2026-10-27 local
time (2026-10-28 UTC). Runtime implementation is not authorized by this draft.

## Requested outcome

Act on mentor feedback: implement Weeks 3–4 with NVIDIA NeMo Guardrails,
evaluations, useful caching, justified TTL/invalidation decisions, and a
back-of-envelope explanation of log volume and MCP tool/payload sizes.
The owner selected **prepare the plan and estimates first**. This artifact
records that planning scope; it does not close tasks 19–34.

## Current baseline

- Tasks 12–18 have recorded completion. Current code revision: `49487b1`.
- The browser, Slack and Week 2 CLI use bounded LangGraph orchestration,
  local RAG, two read-only MCP tools, explicit persistent team preferences,
  and guarded presentation. Browser default remains Local evidence only.
- The core's 512-entry response LRU is not used by `week1.provider.assess`,
  which the Week 2 graph calls. It also has no TTL. Existing persisted passage
  vectors and the loaded encoder do not constitute a query/tool result cache.
- Existing tests/calibration reports do not establish Week 3–4 acceptance or
  production accuracy. In particular, payment timeout retrieval currently
  returns same-service incidents about other mechanisms.

## Success criteria

1. NeMo actually executes at the selected host boundaries; existing credential,
   contract, policy, advisory and source-provenance checks remain enforced.
2. Repeated eligible embedding/tool requests demonstrate a genuine cache hit,
   plus deterministic proof of expiry, source/policy invalidation and isolation.
3. Six upstream query intents have a reproducible automated scorecard, followed
   by independently labeled quality/adversarial cases, an error analysis and
   honest before/after measurements.
4. Correlated, redacted events support the requested dashboard and quantify
   failures, guardrails, memory, cache use, latency, payload size and log volume.
5. Each task has actual acceptance evidence and a private learner note. Human
   review, production authentication, public deployment, posting and a backup
   video require their own observed outcomes; they cannot be inferred.

## Constraints

Surgical changes inside CRA2 and `/tmp`; preserve unrelated local edits and
historical evidence. Preserve the existing loopback launch path, local default,
eight-service synthetic provenance, explicit unknown freshness, team-policy
precedence, and separation of Slack traces from browser Admin. Private owner
audit records remain outside model context, RAG and browser endpoints. Use the
project environment and lockfile; no global installation. Do not send new
provider requests, Slack messages, publish, commit or push as part of planning.

Design and estimates: [spec.md](spec.md). Task sequence and proof:
[plan.md](plan.md). Measurements: [sizing-measurements.json](sizing-measurements.json).

## Owner scope refinement — 2026-10-31

The owner requested a plan to achieve Weeks 3 and 4 one by one, end to end,
then selected **Local demo and complete evidence** as the final target.
Prepare the sequential execution plan now; this request does not accept the
previous design or authorize runtime implementation by itself.

Finish Week 3's local guardrails/cache demonstration before starting Week 4.
Then deliver correlated observability, reproducible evaluations, measured
fixes, a working dashboard, safe failure demonstrations and a timed local
rehearsal. Every task leaves reproducible evidence and a private learner note.
Raj Sam is the owner/reviewer; acceptance is recorded rather than inferred.

Public hosting, Slack delivery, external telemetry and backup video are outside
the selected delivery scope. Original upstream task 34 still requires deployment
and video links: record local completion separately and leave those upstream
items pending. Local evidence mode remains zero-provider and shows no model
risk rating. New live Groq evaluations require a separate provider/payload/budget
decision. See the dated execution refinement in [plan.md](plan.md).
