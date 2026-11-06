# Public corporate evidence integration — 2026-11-05

Scope: 13 reviewed source summaries from nine companies, a validated offline
loader, bounded analogue retrieval, semantic-state provenance, and an Evidence
sources tab. This builds on the P2 action loop and relates to issue #19. It does
not implement a live feed connector, durable cross-process recovery, or a
calibrated failure-probability model.

## Verification

All checks ran locally without live Groq or Slack calls. `uv sync --locked
--offline` completed successfully. Commands use the already synchronized root
and Week 2 environments; `TMPDIR=/tmp` keeps memory fixtures in permitted paths.

| Check | Evidence |
| --- | --- |
| Root offline suite | `TMPDIR=/tmp PYTHONPATH=. .venv/bin/python -m pytest -q -m 'not live'` — 588 passed, 4 live tests deselected |
| Week 1 suite | `TMPDIR=/tmp PYTHONPATH=. week2/.venv/bin/python -m pytest -q week1/tests` — 505 passed |
| Week 2 suite | `TMPDIR=/tmp PYTHONPATH=. week2/.venv/bin/python -m pytest -q week2/tests` — 507 passed |
| Fast policy gate | 20 cases × 5 repeats = 100 assessments; minimum/mean 10/10; all 20 cases repeatable; zero provider attempts |
| Catalog validator | 13 records; 12 incident reports; one change plan; nine companies; no network requests |
| Actual index rebuild | 70 documents / 81 chunks; 46 local incident records / 13 external summaries; cached pinned BGE-small-en-v1.5, 384 dimensions |
| Wheel resource smoke check | Offline wheel build; extraction into an isolated temporary directory; all 13 canonical records and documents load outside the checkout |
| Actual retrieval + MCP integration | Six cases: full/threshold/SAC × local/injected reviewer; actual stdio MCP calls; all completed; no live provider calls |

The [machine-readable integration evidence](public-evidence-integration.json)
records the exact query, source/data hash, original source service, executed
actions and context measurements. The model/embedding implementation was not
changed. The added prompt contract preserves provenance and warns against
turning analogues into local history, policy or causal conclusions.

The actual-source check retrieved Meta's October 2021 report while assessing a
checkout-service worker DNS/backbone change. It verified that the public record
stayed in `documents`, carried its original service, survived context rebuilds,
and did not lower the configured medium risk floor when the offline reviewer
returned a low concern. The reviewer was a deterministic fixture, not a Groq
response. These checks prove integration and contract behavior, not model answer
quality, cost savings or external retrieval recall.

Regression coverage rejects altered URLs, services, kinds and text even with
resealed digests; rejects public evidence promoted to local history, tool
observations or policy; keeps plans separate from incident outcomes; checks
source edits invalidate indexes; and excludes generic multiword requests such
as “configuration rollout” from the meaningful-term admission gate. Existing
service filters, advisory wording, freeze uncertainty and policy behavior stay
covered by the existing suites. Only two existing expectations changed: the
intentional corpus document count and the added UI tab name.

## Limits and remaining work

The data is a manually reviewed snapshot of concise paraphrases and original
annotations. Source text is untrusted, publicly readable articles do not imply
unrestricted reuse rights, and null severity means not extracted into this
collection. Do not infer successful outcomes or failure rates from this sample.
The root CLI's 46-record incident scoring corpus remains separate.

Local browser access was disabled in Work, so no rendered browser screenshot was
verified. Gradio component structure, counts, source links, protected fallbacks,
and compact chat labels passed tests. A local preview attempt could not bind
port 7863; no preview server was left running by this work.

Next increments require source-specific adapters (Google JSON first), individually
verified change outcomes, and incident-level held-out relevance evaluation.
See the [source maintenance guide](../public-evidence.md) for the current
validation/rebuild workflow. The original P0/P1/P2 evidence remains historical;
this addition does not rewrite its measured corpus or baseline.
