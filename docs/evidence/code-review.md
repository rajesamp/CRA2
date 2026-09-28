# CRA2 review and repair record

Review date: 2026-09-28. Baseline: `71eaa3d0d126206d9ede66e6b3d9e62529d84337`
on `rajesamp/CRA2` main. Working branch: `codex/cra2-review-overhaul`.

## Scope and verdict

The baseline inventory contains **28 tracked files, including 8 Markdown files**.
Review covered all six runtime Python modules, both existing test modules, the
evaluation script, five JSON assets, packaging and dependency metadata, CI,
configuration examples, and all eight Markdown files. Three parallel reviews
covered the provider boundary, packaging/CLI, and evaluation/documentation;
integration review covered scoring policy, data consistency, and regressions.

**Baseline verdict: request changes.** The defects below were reproduced or
confirmed against the baseline source and repaired. The resulting local changes
are suitable for review as an advisory prototype. Live provider behavior and
production risk-classification quality have not been established.

## Findings and repairs

Line references in this table refer to the baseline commit, not the edited files.

| Priority | Baseline location | Evidence and consequence | Repair / regression proof |
|---|---|---|---|
| P1 | `cra2/advisor.py:49–64` | An all-`none` model rating in deep mode changes CHG-05 from medium/0.54 to low/0.27; CHG-03 falls from high to medium. The unsure-only floor does not protect confident rule decisions. | Final level cannot fall below the System 1 policy level; all 20 cases tested against a zero-risk model. |
| P1 | `pyproject.toml:19–20`, `cra2/config.py:9`, `cra2/__main__.py:20` | The wheel contains only `cra2/`, while catalog and eval reads target sibling directories. Installed assessment and CLI usage lack required assets. | Bundle canonical JSON inside the wheel, resolve installed resource paths, and load sample cases only when requested. Validate a noneditable installation outside the checkout. |
| P1 | `cra2/system2.py:29–37` | Empty choices raise `IndexError`; absent usage raises `AttributeError`; a response with only one rating is accepted and scored. Server schema settings are not local validation. | Validate the JSON envelope and complete bounded response locally; expected SDK/response failures retain System 1 and known failure usage. Tests include malformed HTTP 200 bodies using the real SDK over mocked HTTP. |
| P1 | `cra2/system1.py:8`, `cra2/advisor.py:16–20` | Whitespace/control-only plans count as present. Invisible plan strings can turn a notification change from medium/0.58 into low/0.23. Non-object inputs and non-string fields also crash. | Normalize whitespace, treat omitted/null plans as missing, reject invisible controls, invalid types, unknown fields/types/modes, and oversized fields. |
| P2 | `cra2/advisor.py:26–30,45–47` | Citation keys allow direct-dependency catalog fields that the model payload does not contain. | Include the direct-dependency catalog in the payload; test that every allowed catalog key resolves to supplied facts. |
| P2 | `cra2/advisor.py:51–53` | A citation-valid comment can still say “Approved. Deploy now.” All model comments precede deterministic hazards regardless of severity. | Validate/filter model text, escape rendered user text, sort comments by severity, and give rule hazards priority on equal severity. This does not prove semantic grounding or eliminate prompt injection. |
| P2 | `cra2/system2.py:18,21–31` | One configured retry permits two HTTP attempts. Cache identity excludes prompt/settings and cache hits reuse original token usage as if newly consumed. | Disable SDK retries; include request settings, schema and prompt in cache identity; distinguish cache hits, attempted requests, missing usage and rejected-response usage. Mocked 429/500 tests require one request. |
| P2 | `scripts/run_evals.py:45–66` | Only the first repeat contributes to rubric/accuracy; failed calls disappear from successful-path counts; incomplete pricing can produce misleading cost estimates. | Score every repeat, report separate request/cache/failure denominators, require both prices, retain known rejected-response tokens, and withhold complete cost estimates when usage is missing. |
| P2 | `scripts/run_evals.py:88–106`, `.github/workflows/ci.yml:24–25` | Reports are written but regressions never cause a failing exit status. A single run is labeled repeatable. | Enforce a minimum score for every assessment, fail requested-provider fallbacks, optionally require repeatability, and use repeated offline evaluations in CI. |
| P2 | `cra2/config.py:10–15`, `tests/test_live_groq.py:18` | Implicit dotenv loading can select unintended credentials; numeric settings accept invalid values; an inherited key alone triggers live test spending/data transfer. | Explicit `CRA2_ENV_FILE`, validated process settings, explicit `CRA2_RUN_LIVE_TESTS=1`, and an offline CI marker filter. |
| P2 | `cra2/__main__.py:20–26` | Sample assets load for every input outside error handling. Empty stdin becomes a literal `-` file read. Oversized/deep JSON and ambiguous duplicate keys lack clear handling. | Lazy sample lookup, bounded input, duplicate-key/nonfinite rejection, and CLI usage errors for bad data. |
| P3 | `cra2/advisor.py:21–23` | A catalog cycle counts the changed service as its own downstream dependent. | A visited set starts with the changed service and prevents self-counting; cycle regression added. |
| P2 | All 8 baseline Markdown files | Broad claims of deterministic model output, fixed latency, exact calls, and complete grounding exceed evidence; line counts and setup instructions become stale. | Rewrite the usage, architecture, ADR, project guidance, prompt, data/eval descriptions, and fast evidence around actual contracts and limitations. |

## File coverage

| Files | Review disposition |
|---|---|
| `cra2/__init__.py`, `cra2/__main__.py`, `cra2/advisor.py`, `cra2/config.py`, `cra2/system1.py`, `cra2/system2.py` | Reviewed and repaired; public result fields gain advisory, uncertainty, policy-floor and provider-accounting metadata. |
| `cra2/prompts/assessment.schema.json` | Strengthened local response contract; provider acceptance still requires a live check. |
| `cra2/rules.json` | Reviewed arithmetic, thresholds, templates and routes; scoring policy retained. No unsupported retuning on the calibration cases. |
| `data/checkout_system.json`, `data/incidents.json`, `evals/cases.json` | Reviewed consistency: 8 services, 10 dependency edges, 16 unique incidents, 20 cases; 5 low / 8 medium / 7 high labels; all five rubric checks appear in every case. Synthetic fixtures retained. |
| `tests/test_cra2.py`, `tests/test_live_groq.py` | Updated intentional API expectations and live opt-in. Added four focused regression modules. |
| `scripts/run_evals.py`, `.github/workflows/ci.yml` | Every-repeat metrics, enforceable gates, bounded reporting, offline test selection, and supported-Python CI matrix. |
| `pyproject.toml`, `uv.lock`, `.python-version` | Wheel contents and test marker repaired; locked dependencies and selected Python retained. No new runtime dependency. |
| `.env.example`, `.gitignore` | Explicit dotenv/live-test opt-ins and broader local-secret exclusions. |
| `README.md` | Setup, input contract, output policy, limitations, and validation commands. |
| `CLAUDE.md` | Maintainable engineering rules and offline/live validation distinction. |
| `cra2/prompts/system_prompt.md` | Treat all context as untrusted data; support auto and deep requests; constrain advisory output. |
| `data/README.md` | Synthetic provenance, graph direction, direct-health scope, and evidence-key limits. |
| `docs/architecture.md` | Actual request flow, policy floor, cache/failure/accounting behavior, and trust boundaries. |
| `docs/adr/adr-001-groq.md` | Provider/model choice, mutable model alias, repeatability limitations, and pending live validation. |
| `docs/evidence/evals-fast.md` | Regenerated with exact UTC window, sample denominator, all-repeat gates, and no unsupported provider-cost claims. |
| `evals/README.md` | Rubric, thresholds, calibration limitation, repeatability and cost interpretation. |

## Validation and remaining limits

The original offline suite passed 36 tests despite the reproduced defects.
The expanded suite checks validation, policy floors, cycles, real SDK request
handling via mocked HTTP, cache identity and accounting, packaging, CLI errors,
and evaluation failure gates. See the regenerated [fast report](evals-fast.md)
for the current 20-case, five-repeat calibration run.

Final local validation on Python 3.13:

| Check | Result |
|---|---|
| `python -m pytest -q` | **221 passed, 4 live tests skipped** |
| Fast evaluation, five repeats, minimum 10 and repeatability required | **100/100** level, route and citation checks; **20/20** cases repeatable; gate passed |
| `uv build --offline` | Source distribution and wheel built successfully |
| Fresh noneditable wheel smoke | Six resource files verified; sample ID, file and stdin passed; missing-key fallback passed |
| Ruff isolated checks (`E4,E7,E9,F,I`) | Passed; Python files formatted consistently |
| `git diff --check` | Passed |
| Local Markdown link check | 9 documents checked, including this report; 12 relative links resolved |

The eight original Markdown files were all updated. Remote CI is configured for
Python 3.10 and 3.13; only Python 3.13 was executed locally in this review.

A fresh isolated virtual environment installed a built wheel and ran sample-ID,
file and stdin assessments from outside this checkout. All six packaged runtime
assets matched their source files. Missing-key deep mode returned the advisory
fallback. This is an installed-package check, not a live provider check.

Dependency audit on 2026-09-28: `pip-audit` examined **20 third-party distributions**
and returned no reported advisories. It skipped one editable local distribution,
CRA2. This covers the installed Python 3.13 dependency set and the database
response at that time, not unknown vulnerabilities or every platform resolution.

A narrow pattern scan read all **28 baseline tracked working files** and found no
matches for private-key blocks, common provider-token forms, or GCP service-account
addresses. Each of the three patterns first detected an in-memory positive canary.
This is not an exhaustive secret scan and does not cover Git history.

Remaining limits:

- Live Groq schema acceptance, latency, repeated-call behavior and costs are
  unverified. The [provider documentation](https://console.groq.com/docs/structured-outputs)
  lists the configured model as supporting strict outputs, but that is not proof
  that this exact request succeeds or that its prose is true.
- The 20 cases were used to tune the rules. Their perfect calibration score is
  not held-out accuracy or production safety evidence. System 1 checks structured
  metadata and plan presence; it does not determine whether arbitrary plan prose
  is adequate. Catalog health is a local snapshot and only direct dependency
  health contributes to the floor.
- Allowed citation keys establish provenance membership, not factual entailment.
  Output text filters detect common unsafe forms and can miss other phrasing.
- The response cache is process-local and bounded by entry count; concurrent
  misses may each make a request. It is not a cross-process cost ledger.
- Remote CI and live tests have not been run by this local review.

## Caveman evidence review

Scope: **unavailable**. No callable Caveman MCP tools or `caveman` executable were
available during this review. No selected Caveman project, report window or trace
IDs were obtained. No payloads or experiments were accessed.

| Evidence bucket | Status |
|---|---|
| Measured provider-complete list-price cost | Not retrieved; unknown. |
| Verified ledger savings | Not retrieved; unknown. |
| Inferred daily headroom | Not retrieved; unknown. |
| Evidence cost | Not retrieved; unknown. |

No cost reduction, Cave Score, causal optimization result, or verified saving can
be concluded from repository inspection or offline evaluations. These buckets
must remain separate. The local token-cost report is explicitly an estimate from
supplied prices and observed usage, not Caveman evidence.

Next read-only check: make the Caveman CLI or MCP available, authenticate if needed
(`caveman login`), explicitly select the CRA2 project, then obtain context and a
bounded report window before querying representative trace metadata. Do not guess
a project or supply an organization ID. Experiment actions remain outside this
evidence-review task.
