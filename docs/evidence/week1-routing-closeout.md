# Week 1 routing close-out

Date: 2026-09-30. Baseline: `ddd0726d185c3af3d1ae3e8adc0d7c1558dfa7bf`. This record describes the local routing changes delivered after that baseline. Historical evidence reports remain intact.

## Fixed failure cases

| Request | Result |
|---|---|
| List risk scenarios in the dataset, titles only | All 45 distinct titles, backed by 46 canonical records |
| List scenarios, titles only; do not assess risk | Title listing; no assessment |
| Show all incident titles | Complete title listing without requiring the word dataset |
| Do not list dataset scenarios; explain what CRA2 does | Help response |
| List titles for nonexistent-api | Explicit unresolved-filter clarification |
| List titles for auth-service and nonexistent-service | Clarification; unknown filter is retained |
| List scenarios with root causes and severity | Literal requested fields from canonical records |
| How many scenarios are in the dataset? | 46 incident records; explicitly distinct-title queries return 45 |

The [local router](../../week1/routing.py) identifies task, operation, and output fields before the [chat adapter](../../week1/chat.py) can inherit service context. Dataset handlers bypass vector retrieval and Groq. Mixed tasks and unsupported scopes/projections clarify. Exact service filters preserve all unknown values. These rules do not establish universal language understanding or classifier accuracy.

## Verification

- Core offline suite: **402 passed**, four live tests deselected.
- Week 1 offline suite: **262 passed**, including **91 new routing regression cases**. The routing tests cover empty, checkout, and auth histories, both UI modes, negation/quotes, counts, literal fields, unknown and mixed filters, mixed tasks, sample service labels, and positive/negative history controls. Repeated variants are correlated regression checks, not independent accuracy samples.
- Required fast evaluation: **100/100** assessments passed, 20 cases × five repeats. Minimum rubric score 10/10; repeatable decision context for all 20 cases; zero provider attempts. This gate checks the existing core risk logic, not broad UI intent accuracy.
- Both locked environments synchronized. Ruff formatting/static checks and Git whitespace checks passed for the changed Python files.
- Clean temporary checkout of commit `601cfbd`: locked Week 1 dependency installation succeeded in a new virtual environment; 262 Week 1 and 402 core tests passed, with four live tests deselected. This automated setup/test smoke check did not provision a fresh embedding index or obtain an independent teammate's attestation.
- GitHub core and Week 1 workflows passed for commit `601cfbd` ([core run](https://github.com/rajesamp/CRA2/actions/runs/36793713492), [Week 1 run](https://github.com/rajesamp/CRA2/actions/runs/36793713502)).
- Existing app-construction, launch-boundary, provider, and credential regression tests passed in the Week 1 suite.
- A fresh local UI process was started on loopback port 7861. Browser automation rejected the localhost visit under its URL policy; a new rendered-screen check was not obtained. Existing earlier screenshots remain historical evidence, not proof of this revision's appearance.

No Jev integration, operational tool, persistent chat storage, or new API credential was added. Normal verification used injected providers and made no paid inference requests.

## Acceptance and status accounting

The owner requested Week 1 closure on 2026-09-30 after these engineering fixes. Record the engineering delivery as complete with the verification above. Named teammate role/read confirmations, whole-team document agreement, independent teammate clone/run, and public sharing/channel posting are separate acceptance evidence and are not inferred from the owner's closure instruction or automated tests.

The maintained weekly status sheet must be updated at its actual location. This evidence file is not a substitute sheet. Its link/path was requested because workspace and accessible Pages searches did not identify it.
