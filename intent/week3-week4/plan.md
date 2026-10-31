# Plan: CRA2 Weeks 3–4

Status: draft for review. Planning only, requested 2026-10-27 local time.
Inputs: [intent](intent.md), [design and estimates](spec.md), pinned upstream
tasks 19–34. No task is complete from this plan alone. No application runtime,
dependency, live process or unrelated working change is modified by planning.

## Order of work and evidence

WIP limit: one numbered task at a time. Each implemented task gets its actual
test/transcript evidence and an ignored `private-learning/task_XX_learner.md`
explaining purpose, code path, a small exercise, and what was verified.

### Week 3: guardrails, then cache correctness and measurement

| Task | Implementation slice | Completion evidence |
|---|---|---|
| 19 | Write `docs/guardrails.md`, mapped to requirement IDs and source limits | Reviewed checklist; allowed help and prohibited decisions distinguished |
| 20 | Resolve/pin NeMo in the existing project environment; integrate local rails around input/context/output while retaining deterministic MCP and policy gates | Actual rail-execution event, positive/negative/error tests, both transports and Week 2 CLI exercised |
| 21 | Approval and unsupported-evidence probes, including detailed-change continuation and payment timeout versus TLS history | Recorded transcripts; no invented risk, approval, live health or edges |
| 22 | Bounded exact query-embedding/retrieval/tool caches with source versions and expiry; current team policy remains authoritative | Real miss then hit; actual RPC count changes; clock-driven TTL, byte-limit, policy/source invalidation and cross-team tests |
| 23 | Benchmark cold, warm and invalidated calls; record per-layer hits and end-to-end latency | Reproducible report with sample count, environment, raw timings and p50/p95; no assumed speed-up |
| 24 | Exercise all six upstream intents against explicit expected behavior, using fresh-session memory and boundary cases | Filled expected/actual scorecard; offline and live-provider results labeled separately |
| 25 | Minimal visible cache indicator plus existing advisory reminder; detailed status/provenance remains in trace | Real browser miss/hit screenshots, expiry proof and preserved chat/trace behavior |

First implementation increment is task 19 only. A compatibility spike precedes
task 20's runtime integration; installation must use the project environment
and lockfile, without changing the root or Week 1 locks. Local mode must remain
zero-provider. If the NeMo dependency conflicts with the verified encoder,
record the conflict and choose an explicit isolated integration design rather
than silently changing the index or weakening local mode.

### Week 4: correlated evidence, evaluations and demo readiness

| Task | Implementation slice | Completion evidence |
|---|---|---|
| 26 | Request/trace ID and stage spans for memory, RAG, cache, MCP, rails, provider and errors | One redacted exported trace; a triggered failure; fresh cache-hit trace without fabricated calls |
| 27 | Automate the six-intent contract scorecard and independent quality/adversarial cases | One-command runner; frozen labeled cases and versioned scorer |
| 28 | Run and retain the baseline before changing quality behavior | Timestamped per-case results and denominators; observed provider usage only |
| 29 | Categorize every failure and rank up to three fixes from the results | Retrieval/tool/rail/support/latency analysis, root cause and priority |
| 30 | Apply justified fixes, preserving the frozen evaluation set | Comparable rerun, quality delta, latency/cache changes, residual failures; no fabricated improvement if baseline is already full score |
| 31 | Local dashboard for actual tool failure, guardrail triggers, effective high-risk flags and cache metrics | Screenshot with real events, rates with denominators, empty/zero distinction and transport filtering |
| 32 | Inject timeouts, corpus absence, ambiguous references, policy/source mutation and storage pressure | Safe fallback transcripts; no stale assessment, crash, leaked data or fail-open |
| 33 | Raj Sam demo: concrete assessment, separate-session memory, cached graph, refusal and scorecard | Script and genuinely timed rehearsal note |
| 34 | Final rehearsal and deployable demo package, with authentic reachability and backup recording evidence | Actual deployment/video links if separately performed; otherwise explicit pending items |

The expanded support tests must include the observed payment-timeout mismatch.
Same-service TLS/NAT/threshold incidents are context, not timeout evidence.
Don't add guessed incidents to force a higher score. An independently authored,
explicitly synthetic timeout example would be a corpus addition with its own
provenance and before/after retrieval evaluation.

## Proposed files and blast radius

These are anticipated implementation paths, not files created by planning.
Change the list when evidence justifies a smaller implementation.

- `docs/guardrails.md`: checklist and requirement mapping.
- `week3/guardrails.py`, `week3/rails/config.yml`, `week3/rails/rails.co`:
  minimal NeMo adapter/configuration and registered local actions.
- `week3/cache.py`, `week3/benchmark.py`, `week3/tests/`: bounded caches,
  injected clock/single-flight, measurements and focused acceptance tests.
- `week2/workflow.py`: rail/cache collaborators at existing boundaries;
  effective policy and source versions propagated through composition.
- `week2/mcp_client.py`: actual transport metrics; preserve reviewed inventory
  checks and deadlines on misses. Tool-level cache avoids repeated execution,
  not validation or source freshness checks.
- `week2/memory.py`, `week2/preferences.py`: only if an explicit revision hook
  is needed; start with authoritative reads to minimize changes.
- `week2/app.py`, `week2/responses.json`: concise cache indicator and linked
  local dashboard; actual per-turn mode and trace remain available in Admin.
- `week2/pyproject.toml`, `week2/uv.lock`: only the resolved, verified NeMo and
  necessary integration dependencies. Preserve existing lock boundaries.
- `week4/telemetry.py`, `week4/evaluate.py`, `week4/dashboard.py`,
  `week4/cases.json`, `week4/tests/`: correlation, bounded redacted records,
  scorecard and local dashboard. Generated telemetry stays local and ignored.
- `docs/evidence/week3-*.md`, `docs/evidence/week4-*.md`: append new evidence;
  do not overwrite historical Week 1–2 or core calibration reports.
- `tasks.md`, `requirements.md`, `week2/README.md`, README final addition:
  narrowly scoped status/requirements/launch updates after the named proof.

Preserve the ten unrelated existing documentation/learning changes. Keep
Slack traces out of Admin, private learner notes/audit data out of Git, and
all generated files within CRA2 or `/tmp`. Add precise ignore rules before
generating any new local state outside existing ignored locations.

## Risks and choices

- NeMo custom local actions first versus model-based self-checks: choose local
  rails initially to preserve local mode and measure added model costs later.
- Exact versioned caches versus semantic answer reuse: choose exact keys;
  a two-digit numeric change must never reuse the opposite assessment.
- In-process versus Redis: choose bounded local caches for the current app;
  revisit shared state only with a demonstrated multi-replica requirement.
- Frozen corpus versus adding synthetic examples: evaluate the mismatch first;
  distinguish retrieval ranking improvements from new coverage.
- Biggest correctness risk: stale policy/evidence across a cache hit or an
  in-flight update. Version-check again before serving, test that race, and
  fail safely rather than silently reusing an assessment.
- Biggest sizing risk: treating one small trace or mean latency as a bound.
  Measure payload tails, burst concurrency, queue waits, storage pressure and
  failure logs before a scale/readiness claim.
- Public auth, external telemetry export, publishing and real deployment
  remain separate concrete choices. The current Admin demo gate is not an
  authenticated production boundary.

## Proof and stop conditions

Before implementation: planning files reviewed; unresolved NeMo package/source
freshness assumptions visible. During implementation: focused deterministic
tests, then the Week 2 gate and unchanged core/Week 1 checks when integration
warrants them. Preserve the required repeated fast core evaluation, while
labeling it calibration rather than the new Week 4 quality score.

Don't run new provider calls to produce a planning baseline. Obtain an exact
provider/payload/budget decision before a new live evaluation batch. Offline
reviewer doubles are useful integration proof, not live quality evidence.
Don't send Slack messages, deploy, commit, push or publish from this plan.

Tasks close individually only after named artifacts and observed evidence
exist. A plan, package import, cache-hit badge, test double or hypothetical
capacity number is not end-to-end acceptance. The stage chain remains draft;
this planning turn does not self-approve later implementation stages.

## Sequential local execution plan — 2026-10-31

**Current review draft.** This section refines the earlier proposal following
the owner's request to finish Weeks 3 and 4 one by one and their selection of
**Local demo and complete evidence**. No task is implemented or self-approved
by planning. The pinned upstream task list was re-read through the GitHub
connector on this date. The earlier intent/spec remain proposals, with their
dated local-scope additions governing this revised delivery target.

### Outcome and execution loop

User story: Raj Sam describes a concrete service change in local chat, reviews
grounded incident/tool evidence under current policy, sees why approval is a
human decision, repeats a dependency query with verified cache reuse, and
opens the trace, dashboard and evaluation results from the UI.

Reuse the Week 2 app/graph, corpus/index and both MCP tools. Preserve local
zero-provider operation, synthetic provenance, unknown production freshness,
policy precedence and credential boundaries. Hosting, video, external telemetry,
Slack posting and new live-provider evaluations are outside this selected scope.

One task active at a time: **Ready → In progress → Verify → Review → Done**,
or **Blocked** with the specific missing prerequisite. Discuss purpose, files,
risks and acceptance proof before implementation. Complete an accepted task's
routine reversible work without repeated permission requests. Record owner
acceptance before beginning the next numbered task; do not silently widen it.
Owner/reviewer: Raj Sam. Follow the artifact-chain commit workflow when
authorized, preserving unrelated edits. This planning draft does not authorize
a commit, push, merge or publication.

Every close-out records scope, changed files, exact commands/results, revision
and dirty-diff/source identity, limitations, evidence link and private learner
note. A task is Done only after its deliverables and named proof exist. Keep
external and human acceptance separate from engineering verification.

### Week 3 — guardrails and caching, then milestone acceptance

| Task | Implementation slice | Required proof before moving on |
|---|---|---|
| 19 | Requirement-mapped `docs/guardrails.md` checklist: allowed assistance, prohibited decisions, evidence limits, enforcement points and failure behavior | Rule → requirement → enforcement point → allowed/prohibited example → expected outcome; owner review. Documentation only in this task. |
| 20 | Compatibility spike, exact NeMo pin, then actual local input/context/output rails at the existing workflow boundaries | Lock diff and unchanged encoder fingerprint; real rail events; allow/refuse/error cases; zero local provider attempts; UI, CLI and offline Slack adapter checks. Importing a package alone is insufficient. |
| 21 | Approval and unsupported-evidence probes against the integrated workflow | Bare approval refusal; approval plus concrete change continues permitted review; absent/mechanism-mismatched evidence yields no invented score. Record actual outputs, including payment timeout versus unrelated TLS history. |
| 22 | Bounded exact query-vector/retrieval/tool caches at existing collaborator boundaries | Actual miss/hit and fewer MCP executions; fake-clock TTL; source/contract and preference/config mutation; in-flight invalidation; exact-number distinctions; team isolation; entry/byte bounds and bounded concurrent work. Never cache failures or replay old traces. |
| 23 | Benchmark actual repeated graph-query behavior and individual cache layers | At least 30 measured trials per condition, startup separately; disabled/empty/warm/expired or invalidated conditions; raw times, p50/p95, hit denominators, actual RPCs and environment/source identity. Investigate no improvement before acceptance. |
| 24 | Run all six source intents locally end to end and correct defects | Six-row expected/actual scorecard: concrete checkout change, similar incidents, freeze uncertainty, payment dependents, separate-session memory, approval refusal. Real local RAG/MCP; fresh-process memory and different-team control; no local model rating. |
| 25 | Visible advisory reminder and truthful per-request cache badges in the existing chat | Real browser miss/hit screenshots, expiry demonstration, refusal/continued review and preserved evidence/trace behavior. Badge state must agree with actual events. |

Task 20 tries the existing `week2` environment first. If NeMo conflicts with
Python/FastEmbed or the dependency set, document the conflict and present an
isolated adapter option before integration. Do not silently change the index,
encoder or root/Week 1 locks. Failed/missing required rails must not permit an
unguarded assessment. Preserve the reviewed two-tool metadata gate.

Cache starting values remain proposals from the spec: query-vector retention
24 hours; retrieval/synthetic-tool retention five minutes; 1,024 entries and
16 MiB per cache. Read policy/preferences authoritatively per request and check
source versions on reuse and before serving in-flight results. Final-answer
caching and Redis stay deferred. `build_workflow` currently builds per request:
prove an injected/host-owned cache survives repeated requests while protected
team state remains isolated. Trace each hit as reuse, never an invented RPC.

**Week 3 exit:** tasks 19–25 accepted; six local contracts passing; actual NeMo
and miss/hit/expiry evidence; no observed blocking safety failure in the stated
acceptance cases; preserved regression checks; successful browser walkthrough.
Fix a failed exit check in this week before starting task 26. Local success
does not establish live model quality or current production health.

### Week 4 — observability, evaluation, improvement and rehearsal

| Task | Implementation slice | Required proof before moving on |
|---|---|---|
| 26 | Extend the current request ID into stage spans and bounded redacted local telemetry | Success, cache-hit and triggered-failure traces correlate memory/RAG/cache/rails/actual tools/provider status/output. Redaction and storage failure tested; no fabricated call on a cache hit. |
| 27 | One-command automated six-intent scorecard and additional labeled cases with a versioned scorer | Frozen case/source/scorer hashes, human-reviewed quality labels, development/validation/reserved separation, nonzero exit on gate failure, and a known-failing canary proving detection. |
| 28 | Retain the Week 4 baseline before quality fixes | Timestamp, per-case pass/fail and denominator, revision/diff/corpus/config, mode, cache state, timings and actual provider attempts. Label this a post-Week-3 baseline. |
| 29 | Categorize every failure and prioritize up to three justified fixes | Case/expected/actual/category/root cause/impact/narrow fix/regression proof table. Cases inspected for tuning become regression evidence. Report zero failures honestly if observed. |
| 30 | Apply measured fixes and rerun the unchanged comparable scorecard | Before/after scores with denominators and raw results, latency/cache changes and residual failures; reserved cases evaluated after choices freeze. Zero quality delta requires explicit review of any revised improvement criterion. |
| 31 | Local dashboard linked from the UI | Real tool failure, guardrail trigger, high-risk preference, cache and latency data with windows/denominators; zero versus missing distinguished; transport filtering and private-data separation verified; browser screenshot/link. |
| 32 | Trigger required faults with isolated fixtures | Transcripts for MCP timeout, ambiguous “this change,” absent/mismatched corpus support, in-flight source/policy mutation, unavailable rails and full/unavailable telemetry storage. Safe fallbacks; no deletion of real owner records. |
| 33 | Raj Sam demo script and timed rehearsal | 2–3 main queries plus memory, repeated graph query, refusal and scorecard/dashboard beats; actual elapsed time, reset steps and known limitations. Provisional five-minute local slot unless the owner specifies another. |
| 34 | Verify local launch instructions and run final end-to-end rehearsal | UI/dashboard reachable locally; fresh-process demo with isolated state; saved walkthrough/screenshots/reports; reproducible launch/reset instructions. Record local acceptance separately from pending upstream deployment/video links. |

For task 31, define tool failure rate as failed / attempted actual MCP calls;
high-risk preference application as applied / eligible memory reads, separate
from configured floors; cache hits / eligible lookups per layer. Count guardrail
triggers by stage/outcome. Label fault-injection run sets separately from normal
demo traffic. Trace/user IDs are not aggregate metric labels.

Freeze scorer/case/source versions before baseline. Development/validation cases
guide fixes; reserved cases are evaluated after choices freeze. Once a reserved
case is inspected to select a fix it becomes regression evidence, requiring
new independent cases for further quality claims. Never tune the rubric or
remove unfavorable samples to inflate improvement. If baseline is perfect,
report zero delta and propose owner-reviewed acceptance of maintained quality
plus measured operational gains; do not claim the upstream improvement
criterion was met without such evidence.

**Week 4 local exit:** six contracts remain 6/6; zero observed blocking safety
failures in the enumerated acceptance cases; baseline/rerun and residual failures
retained; chat-to-dashboard navigation works; a fresh-process timed rehearsal
completes. Rerun final scorecard/affected gates after any late task-32 or later
code fix. Do not claim public reachability, independent teammate acceptance,
production accuracy or complete upstream task-34 deployment/video delivery.

### Evidence, regression gates and current board

Per-task evidence lives at `docs/evidence/week3-task-19.md` through
`week3-task-25.md`, then `week4-task-26.md` through `week4-task-34.md`. Each file
links actual logs, sanitized benchmark/evaluation reports and screenshots.
Private notes remain in ignored `private-learning/task_XX_learner.md` and explain
purpose, code path, a small exercise and observed results. Add precise ignore
rules before generating new private telemetry; never expose owner audit data.

Task 19 proposes any needed W3/W4 requirement IDs with explicit mappings; add
accepted IDs to `requirements.md` without rewriting history. Update `tasks.md`
and `docs/weekly-tracker.md` only for observed changes. Final README additions
describe local launch/dashboard/evidence and pending external upstream items.

Run focused tests for each implementation. At integration/milestone boundaries,
run the existing gates and record actual counts rather than copying old counts:

```sh
uv run --locked --offline --project week2 python -m pytest week2/tests -q
uv run --locked --offline pytest -q -m 'not live'
uv run --locked --offline --project week1 python -m pytest week1/tests -q
uv run --locked --offline python scripts/run_evals.py --mode fast --repeat 5 --require-repeatable --out /tmp/cra2-week34-fast.md
```

Add focused `week3/tests` and `week4/tests` commands once those files exist.
These are future commands, not tests run during planning. Browser verification
is required for tasks 25, 31 and final rehearsal. Slack adapter verification
uses offline doubles, not actual messages. Missing models/packages require an
explicit setup step; offline verification does not implicitly provision them.

| State | Tasks |
|---|---|
| Review | Revised intent/spec/plan; owner acceptance not yet recorded |
| Ready after plan acceptance | 19 |
| Backlog, dependent on prior acceptance | 20–34 |
| Implemented/verified by this planning turn | None; planning artifacts only |
| External upstream items outside selected scope | Task-34 deployment/video; prior Week 1 human acceptance |

Next implementation slice: **task 19, guardrail checklist only**. Review the
rule/requirement/enforcement/example/outcome mapping before task 20 code.

## Execution authorization — 2026-10-31

The owner accepted the plan ("looks good lets move") and requested learning
alongside progress while occupied in meetings. Proceed sequentially with
routine implementation, verification and evidence without waiting for a reply
after every numbered task. This standing authorization supersedes the earlier
per-task wait in the execution loop; retain task boundaries and report progress.
Escalate only a material change of scope or a required external/payload decision.
Local delivery, privacy and no-new-provider/no-posting boundaries remain.
Learning updates explain what a component does, alternatives, tradeoffs and
what actual checks prove. Private per-task notes remain ignored.
