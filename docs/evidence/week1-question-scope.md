# Week 1 question scope

Date: 2026-09-30 (America/Chicago). Baseline: `99c89316bf8915efc945713af1878b6e324061c6`.

## Failure and cause

The user asked `what is the username of this app?`. Their screenshot shows a catalog-service clarification and unrelated incident evidence. A baseline replay with an empty injected retriever returned `needs_clarification` after one retrieval call. Unrecognized requests had no scope check and always entered the change-assessment path. The previous capabilities fix handled help phrases but left this default intact. Groq did not produce the wrong clarification.

## Response contract

Credential, shape, length, control-character, and mode checks run first. The [local router](../../week1/routing.py) then classifies the active request into two scopes before history or retrieval:

| Scope | Behavior |
|---|---|
| `cra2` | Use the supported help, dataset, change-review, historical-comparison, or advisory/Week 2 boundary handler. Clarify ambiguous changes and unsupported dataset filters. |
| `non_cra2` | Return only `Not really a CRA2-related question. See the CRA2 GitHub repository.` The repository text is a fixed link to `https://github.com/rajesamp/CRA2`. No evidence or provider request. |

“Related” means a supported product intent, not simply the presence of CRA2 or a catalog name. App usernames/account metadata have no supported lookup and receive the fixed response. No identity is inferred from the repository owner, environment, or conversation. Recognized CRA2 tasks take precedence over unrelated chatter, without answering that chatter. Quoted examples, negated requests, and old service history cannot supply scope for an unrelated active request.

The [chat handler](../../week1/chat.py) records the scope in the trace. Known-key rejection still occurs first. Invalid input is a validation response, not a scope classification. The existing change-detail vocabulary is shared by scope and specificity checks. No provider, dependency, model, dataset, live tool, or persistent history feature was added.

## Verification

- **449 Week 1 tests passed**, including **121 additional tests**. Sixteen unrelated/unsupported forms are checked across both UI modes and three histories, with retrieval/provider calls prohibited. Positive controls cover help, inventory, valid/vague changes, true follow-ups, unknown services, historical comparison, current-state deferral, preferences, and the approval boundary. A credential canary and the actual UI display wrapper are included.
- The small, declared scope regression set has **39 distinct questions**. Actual CRA2: 23 classified CRA2, zero classified non-CRA2. Actual non-CRA2: zero classified CRA2, 16 classified non-CRA2. These are development regressions, not a held-out accuracy estimate or a calibrated classifier score.
- **402 core tests passed**, four live tests deselected. Both locked environments synchronized offline. Ruff formatting/static checks passed.
- Exact configured-secret checks found zero matches in **91 tracked/non-ignored working-tree files** and **one private UI log**; a detection canary passed. The ignored `.env` and log have `0600` permissions. Documentation changes to `tasks.md`, `requirements.md`, and the Week 1 README were verified as appends. Evidence links and Git whitespace checks passed. Secret-scan coverage is those configured values and files, not every possible destination.
- Required fast evaluation: **100/100** assessments, 20 cases × five repeats, minimum rubric score 10/10, all 20 decision contexts repeatable, zero provider attempts. UTC window: `2026-10-01T00:26:22.187524+00:00` to `2026-10-01T00:26:22.245481+00:00`. This evaluates core advisory behavior; it does not measure free-text scope accuracy.

## Limits

This is a bounded rule parser. Unrecognized forms receive the repository response and may include legitimate CRA2 questions outside the tested syntax. Some overlapping vocabulary can still be misclassified. The fixed out-of-scope response prevents retrieval/model generation for rejected inputs; it does not prove perfect scope recognition. Add failing real prompts as regressions before widening the contract.

The earlier browser URL-policy rejection prevents an automated rendered screen check. The real UI handler is covered offline; no new browser screenshot is claimed. Previous evidence reports remain historical.
