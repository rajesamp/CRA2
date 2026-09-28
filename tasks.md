# CRA2 task alignment: Week 1 only

Source: [ChangeRiskAdvisor task plan](https://github.com/abhineer/Sep-Projects/blob/3e52f28ae1f430211d2df6098ab366f38ebdb86e/ChangeRiskAdvisor/tasks.md), upstream commit `3e52f28ae1f430211d2df6098ab366f38ebdb86e`, file blob `779eb7e95446ac97f3be4c30f65396ab2e343e02`. The identifiers below retain upstream task numbers 1–11. Tasks 12–34 and optional stretch work remain outside this iteration. [Requirements](requirements.md) explain policy and persona mappings.

Status distinguishes an artifact from its human acceptance: **implemented** means code/data exists with recorded checks; **draft** means a written deliverable awaits review; **partial** means a specific external acceptance item remains. No box implies an unobserved human action.

| # | Week 1 deliverable | CRA2 artifact / evidence | Acceptance status |
|---|---|---|---|
| 1 | Roles, requirements reading, stack agreement | [Team record](docs/team.md) | Draft; named role assignments, individual reading confirmations, and stack agreement pending |
| 2 | Narrative six-pager | [Six-pager](docs/6-pager.md) | Draft; whole-team review/agreement pending |
| 3 | Customer-view release and customer/internal FAQ | [PR/FAQ](docs/pr-faq.md) | Draft; whole-team review/agreement pending |
| 4 | Remote repo, feature-branch process, runnable README | Existing [README](README.md), append-only Week 1 instructions, isolated lockfile | Setup exists; independent teammate clone/run confirmation pending |
| 5 | Advisory, evidence-citing prompt and two manual cases | Existing [prompt](cra2/prompts/system_prompt.md) plus [Week 1 addition](week1/prompt.md); [demo evidence](docs/evidence/week1-demo.md) | Implementation present; verification status recorded in evidence, not assumed from prompt text |
| 6 | Synthetic incident, graph, and health dataset | Existing [data guide](data/README.md), 8 services / 10 edges / 16 synthetic incidents; 30 separately labeled samples | Dataset foundation present; six catalog services have multiple synthetic incidents, two have one |
| 7 | Incident/postmortem/runbook corpus spanning six intents | [Corpus manifest](week1/corpus/manifest.json), 6 derived synthetic postmortems, 5 runbooks, existing incident records | New corpus added; inventory and source boundaries recorded in alignment evidence |
| 8 | Chunking, embedding, persisted vector index | [Retriever](week1/retrieval.py), [ingestion evidence](docs/evidence/week1-retrieval.md) | Verify actual counts/model/digest in evidence; generated store is local and ignored |
| 9 | Relevant top-three checkout-config retrieval | [Retrieval evidence](docs/evidence/week1-retrieval.md) | Query/passages and explicit relevance judgments recorded; not a universal retrieval-quality claim |
| 10 | Free-text description to grounded assessment | [Chat adapter](week1/chat.py), [demo evidence](docs/evidence/week1-demo.md) | Detailed-query and limitation behavior recorded separately |
| 11 | Local Gradio demo, screenshot, shared link | [UI](week1/app.py), [launch instructions](week1/README.md), [demo evidence](docs/evidence/week1-demo.md) | Local verification recorded there; public sharing and posting to a team channel remain pending |

## Human acceptance still required

- Confirm the owners, requirements reading, and stack in `docs/team.md`.
- Review and agree on `docs/6-pager.md` and `docs/pr-faq.md`.
- Have a teammate follow the documented setup from a fresh clone and record the result.
- Review the local UI, then choose whether to enable authenticated public sharing and identify the team destination. No message has been posted on the team's behalf.

## Append-only delivery rule

Files that existed at baseline `6adb5664ba974b590a9bd8e4c40242a02d740404` keep their full original content. The README may gain a final Week 1 section. New files can supply missing capabilities; the root package, root dependency lock, existing tests, and historical evidence are not rewritten. Verification compares baseline bytes and checks that every changed pre-existing file begins with its complete baseline content.
