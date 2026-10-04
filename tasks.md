# CRA2 task alignment: Week 1

Source: [ChangeRiskAdvisor task plan](https://github.com/abhineer/Sep-Projects/blob/3e52f28ae1f430211d2df6098ab366f38ebdb86e/ChangeRiskAdvisor/tasks.md),
upstream commit `3e52f28ae1f430211d2df6098ab366f38ebdb86e`, blob
`779eb7e95446ac97f3be4c30f65396ab2e343e02`. Task numbers 1–11 retain upstream
identifiers. Tasks 12–34 and optional stretch work stay outside this
iteration. [Requirements](requirements.md) maps policy and personas.

**Status vocabulary.** *Implemented* means code/data exists with recorded
checks. *Draft* means a written deliverable awaits review. *Partial* means a
specific external acceptance item remains. No box means an unobserved human
action.

## Week 1 deliverables

| # | Deliverable | Artifact / evidence | Status |
|---|---|---|---|
| 1 | Roles, requirements reading, stack agreement | [Team record](docs/team.md) | Draft; role assignments, reading confirmations, stack agreement pending |
| 2 | Narrative six-pager | [Six-pager](docs/6-pager.md) | Draft; whole-team review pending |
| 3 | Customer-view release, customer/internal FAQ | [PR/FAQ](docs/pr-faq.md) | Draft; whole-team review pending |
| 4 | Remote repo, feature-branch process, runnable README | [README](README.md), Week 1 instructions, isolated lockfile | Setup exists; independent teammate clone/run pending |
| 5 | Advisory evidence-citing prompt, two manual cases | [Prompt](cra2/prompts/system_prompt.md) + [Week 1 addition](week1/prompt.md); [demo evidence](docs/evidence/week1-demo.md) | Implemented; verification recorded in evidence, not assumed |
| 6 | Synthetic incident, graph, and health dataset | [Data guide](data/README.md): 8 services, 10 edges, 16 incidents, 30 samples | Dataset present; six services have multiple incidents, two have one |
| 7 | Incident/postmortem/runbook corpus for six intents | [Corpus manifest](week1/corpus/manifest.json): 6 postmortems, 5 runbooks, incident records | Added; inventory and boundaries recorded in alignment evidence |
| 8 | Chunking, embedding, persisted vector index | [Retriever](week1/retrieval.py), [ingestion evidence](docs/evidence/week1-retrieval.md) | Verify counts/model/digest in evidence; generated store local and ignored |
| 9 | Relevant top-three checkout-config retrieval | [Retrieval evidence](docs/evidence/week1-retrieval.md) | Query/passages and relevance judgments recorded; not a universal claim |
| 10 | Free-text description to grounded assessment | [Chat adapter](week1/chat.py), [demo evidence](docs/evidence/week1-demo.md) | Detailed-query and limitation behavior recorded separately |
| 11 | Local Gradio demo, screenshot, shared link | [UI](week1/app.py), [launch instructions](week1/README.md), [demo evidence](docs/evidence/week1-demo.md) | Local verification recorded; public sharing/posting pending |

## Human acceptance still required

- Confirm owners, requirements reading, and stack in `docs/team.md`.
- Review and agree on `docs/6-pager.md` and `docs/pr-faq.md`.
- Have a teammate run documented setup from a fresh clone and record the result.
- Review the local UI, then decide on authenticated public sharing and the
  team destination. No message has been posted on the team's behalf.

## Append-only delivery rule

Files that existed at baseline `6adb5664ba974b590a9bd8e4c40242a02d740404` keep
their full original content. The README may gain a final Week 1 section. New
files can add capabilities; the root package, root lockfile, existing tests,
and historical evidence are not rewritten. Verification compares baseline
bytes and checks that every changed pre-existing file begins with its complete
baseline content.

## Owner close-out — 2026-09-30

**Week 1 engineering delivery: complete.** The owner closed the milestone after
the routing fixes. [Close-out evidence](docs/evidence/week1-routing-closeout.md)
records the fixes, 402 core and 262 Week 1 passing offline tests, and the
repeated core evaluation. Dataset routing now handles the reported negation,
scope, count, and field-projection failures without a classifier API.

The table above stays the historical acceptance record. Owner closure does not
attest teammate reviews, a fresh-clone run, or public sharing/channel posting.
Keep those confirmations as follow-up evidence. The weekly status sheet update
is a separate action at the sheet's actual location.

## Week 1 maintenance — question scope, 2026-09-30

The app-username report exposed an unrestricted fallback to change assessment.
A local scope check now gives unrelated/unsupported questions only the
repository response, before history, retrieval, or Groq. Supported CRA2 tasks
keep existing handlers and safeguards.
[Scope evidence](docs/evidence/week1-question-scope.md) records 449 passing
Week 1 tests, 402 passing core tests, and the required 100-assessment fast
evaluation. Historical records above stay intact; human confirmations and the
weekly sheet still need their actual evidence/location.

## Week 2 continuation — 2026-09-30

The owner authorized tasks 12–18, each discussed in order before
implementation. This supersedes the earlier Week 2 deferral; Weeks 3–4 and
stretch work stay deferred. Week 1 engineering is complete; its human
acceptance is pending. Task 12's proposed scope was accepted in chat.

| # | Deliverable | Artifact / evidence | Status |
|---|---|---|---|
| 12 | Design health and dependency tool contracts | [Tool contracts](docs/tools.md) | Spec delivered; fixture/example verification recorded |
| 13 | Implement system-health tool | Known/unknown-service test log | Done; see below |
| 14 | Implement dependency-graph tool | Known/unknown-service test log | Done; see below |
| 15 | Expose both tools through MCP | Actual agent/tool round-trip trace | Pending discussion; resolve Sentinel metadata screening |
| 16 | Design memory schema, verify readback | Schema and write/read log | Pending task discussion |
| 17 | Integrate team risk-appetite memory | Two separate session transcripts | Pending task discussion |
| 18 | Expandable Gradio agent trace | Screenshot of actual calls and recalled settings | Pending task discussion |

Tool invocations read explicitly labeled synthetic snapshots; they do not make
the fixture current production evidence. Unknown active incidents and freshness
stay unknown. Advisory behavior, evidence grounding, credential protection,
team-policy precedence, and configurable `week1/responses.json` answers remain
required. Jev integration is out of scope.

## Week 2 tools delivered — 2026-09-30

| # | Delivery | Evidence |
|---|---|---|
| 13 | `check_system_health` implemented: validated snapshot facts, safe errors | [Test log](docs/evidence/week2-tools.md) |
| 14 | `get_dependency_graph` implemented: both directions, cycle-safe traversal | [Test log](docs/evidence/week2-tools.md) |

Both functions are callable from [week2/tools.py](week2/tools.py). No
dependency or existing runtime file changed. Task 15's MCP/agent wiring, tasks
16–17's persistent memory, and task 18's UI trace remain pending. Week 1 human
acceptance remains pending.
