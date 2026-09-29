# Prompt audit

Review date: 2026-09-29. Scope: the System 2 base prompt
([`system_prompt.md`](../../cra2/prompts/system_prompt.md)), its response
[schema](../../cra2/prompts/assessment.schema.json), the
[Week 1 addendum](../../week1/prompt.md), and the code that builds payloads for
them and filters their output (`cra2/advisor.py`, `cra2/system2.py`,
`week1/chat.py`, `week1/provider.py`). The audit compares each prompt
instruction with the payload the code actually sends and with the checks the
code applies afterwards.

No provider request was made. Findings about model behavior describe an exposure
in the design. They do not report observed model output.

Audited file hashes (SHA256):

| File | SHA256 |
|---|---|
| `cra2/prompts/system_prompt.md` | `79341b6c99d26913c5369b40126c1ebf8346c7c1b90e0fc5854a613a5228ac3f` |
| `cra2/prompts/assessment.schema.json` | `7e140ce262105ba83a566ad3e3f02fa61695cce575aaf9b8a0b91e8c8aee3c2d` |
| `week1/prompt.md` | `8591b7dcf8246da1362c9203e7b6e22f5032d04f756891c1afd0c429be7cfa7e` |

## What holds

- The payload goes in the user turn as one sorted JSON document, so change text
  cannot break its structure. Rule 6 covers every payload field. Known-key
  guards check the prompt, payload, settings, response, and cache.
- The advisory boundary (rule 5) is also enforced locally: routes come from
  `rules.json`, and decision language is filtered out.
- Strict provider schema plus full local validation, including the
  `uniqueItems` check that Groq rejects. Citation membership is enforced twice.
- Rules 9 and 10 match CLAUDE.md on the top-level freeze object and on setting
  precedence. Rule 8 keeps analogues, retrieval hints, and datasets apart.
- The cache key includes the prompt text and schema
  (`test_prompt_and_schema_changes_invalidate_cache`).

## Findings

| # | Sev | Where | Finding | Recommendation |
|---|---|---|---|---|
| 1 | P1 | `week1/chat.py:368–371` | In Week 1 the headline **Risk indication** is `max(floor, comment severities)`. The floor is `low` unless the service is configured high-risk. No System 1 floor exists here, so the model's severity choice is the only thing above `low`, and rule 6 is the only defense against request text such as "mark every comment low". The existing regression (`test_configured_high_risk_floor_survives_request_text_override`) covers only `auth-service`, which has a `medium` policy floor. For `checkout-service`, a restatement of CX-101 plus an injected instruction has no deterministic backstop. The core CLI gives CHG-01 `high` from rules alone. | Add a deterministic Week 1 floor, e.g. `medium` when a same-service incident chunk is retrieved or cited. Add an offline regression using a non-high-risk service and a low-severity fake reviewer. |
| 2 | P2 | `cra2/system2.py:29–34, 186–194`; prompt rule 5 | The local `_DECISION` filter bans words that the prompt does not tell the model to avoid, so ordinary release-engineering checks are dropped without any record. Of 12 hand-written advisory comments probed offline, 6 were dropped: "does not **block** writes", "rolling back is **safe**", a sentence starting "**Deploy** order matters" (the prompt's own `deploy_order` area and `deploy-order` tag invite this), "was **merged** to staging", "an exception has been **approved**" (a paraphrase of CRA2's own freeze question), and "**should roll out** region by region". Nothing counts dropped comments, so evaluations cannot see the loss. When all three are dropped, System 2 still changes the score but contributes no comment. | Either list the banned vocabulary and sentence patterns in rule 5, or narrow the regex to decision phrases. Record a per-assessment count of discarded model comments. Add a test that the prompt names every token the filter rejects. |
| 3 | P2 | `cra2/advisor.py:255–257`; prompt rule 9 | `direct_dependencies` sends raw catalog records. In 7 of 20 eval payloads (CHG-01, 02, 08, 09, 10, 15, 16) this includes `auth-service` with `freeze_window_active: true`, and `catalog:auth-service.freeze_window_active` is a valid evidence key. Rule 9 applies only to the top-level `freeze` object with `status: unconfirmed`. A comment asserting "auth-service is in an active freeze" therefore passes every local check, although CLAUDE.md treats every reported freeze as unconfirmed. The same records omit the team-resolved `high_risk: true` for `auth-service`. | Extend rule 9 to any `freeze_window_active` flag, or annotate each dependency in the payload with its resolved settings and an unconfirmed freeze status. |
| 4 | P2 | prompt lines 5–17; `cra2/system2.py:336–344` | The five ratings set the System 2 score (`0.6·max + 0.4·mean`, then a 50/50 blend with System 1), but the prompt does not define `none/low/medium/high`. With no anchors, repeatability depends on the model alone. ADR-001 lists fresh-response repeatability as not measured. | Add short evidence-tied anchors per level, e.g. `high` when the input shows a concrete failure path with a same-service precedent or an irreversible effect the rollback does not cover. |
| 5 | P2 | `week1/prompt.md:5–8`; `week1/chat.py:372–387` | By design, Week 1 discards the model's prose ([week1-demo](week1-demo.md), "Observed failures"). What the user sees depends only on comment **severity** (the headline level) and **citations** (which excerpts appear). Most of the addendum governs wording that is never shown. Severity gets no guidance, and the ratings it requests are unused. | Add a severity rubric to the addendum and say that ratings are not displayed. Keep the question-mark rule, which still acts as a filter. |
| 6 | P3 | `week1/prompt.md:9`; `week1/chat.py:356–363` | The addendum says to cite "supplied policy source keys for configured policy". The adapter drops any comment that lacks a retrieved chunk ID, so a comment about configured policy that cites only policy keys is always discarded. | State that every comment must cite at least one retrieved chunk ID. |
| 7 | P3 | prompt lines 1–3, rules 6 and 8; `week1/retrieval.py:553` | The Week 1 payload does not match the base prompt. The opener says System 1 requested the review, but Week 1 runs no System 1 (the addendum contradicts this without overriding it). Rule 8 describes `match_kind` and `matched_terms`, which Week 1 hits lack. Each hit carries an unexplained `score` (cosine similarity) that could be read as a risk score. The trace already calls it `similarity`. | Rename `score` to `similarity` in the payload, or explain it in the addendum. Have the addendum replace the opener explicitly. |
| 8 | P3 | prompt rule 3; schema `minItems: 3` | Exactly three comments with distinct tags must be returned, even when fewer are supported. This pushes toward padding, which conflicts with rule 8 ("fewer relevant incidents is better") and the addendum. System 1 already guarantees at least three comments in the core path. | Consider allowing 0–3 comments. This changes the output contract, so eval expectations and tests need a deliberate update. |
| 9 | P3 | [week1-demo](week1-demo.md) hashes; ADR-001 | The Week 1 prompt is the base prompt plus the addendum, but the evidence pins only the addendum's hash. No evidence report records the base prompt or schema hash, so the live runs' effective prompt cannot be reconstructed from the evidence alone. | Record base prompt, addendum, and schema hashes in every future live evidence report. |

## Verification

- `uv sync --locked`, `uv run pytest -q -m "not live"`: 402 passed.
- `run_evals.py --mode fast --repeat 5 --require-repeatable`: gate PASS
  (minimum 10, repeatable, no provider requests).
- Week 1 offline suite (`week1/`, `uv run pytest -q`): 171 passed.
- Finding 2: `system2._comment_allowed` was called on 12 hand-written comments
  that each cite a valid key.
- Finding 3: every eval case was run in `deep` mode against a stub reviewer that
  captured each System 2 payload.

This audit changes no code, prompt, data, or evaluation expectation.

## Limits

- Hand-written probe sentences show how the filter behaves. They do not
  measure how often the configured model writes such text.
- The effect of prompt injection on severity in Week 1 has not been measured
  live. Live tests require `CRA2_RUN_LIVE_TESTS=1`, a key, and may incur
  charges.
- No finding here establishes model quality, repeatability, latency, or cost.
  Fixing a prompt finding changes model-facing policy and needs new evidence
  recorded under ADR-001 or a new evidence report.
