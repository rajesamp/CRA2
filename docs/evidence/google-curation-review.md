# Google incident curation review

Reviewed November 5, 2026, from the eight candidates collected by the
[staging increment](google-incident-import.md). This is assistant source review
prepared for human review in a draft PR, not independent human approval.
The full first-party reports and update histories informed concise canonical
paraphrases. The importer did not promote or approve candidates.

Six additions bring `data/public_evidence.json` to 19 records: 18 incident
reports and one staging change plan across nine companies. The original 13
records, 46 local incident records and service catalog remain unchanged.

| Source report | Decision | Added review coverage |
|---|---|---|
| [Vertex AI, February 27](https://status.cloud.google.com/incidents/41E5S3mkTGDfkZuJZH5k) | Include | Request-shape coverage and shared dependency capacity |
| [VMware Engine, July 14](https://status.cloud.google.com/incidents/T8gmtofFSTGT5tbhyciF) | Include | Private-address data-path verification |
| [us-west1 network, August 20](https://status.cloud.google.com/incidents/utF3FMFdQfwBzJcGG6vf) | Include | Maintenance bandwidth and recovery backlogs |
| [Router maintenance, September 1](https://status.cloud.google.com/incidents/J5ia5t9p3g9Q5Wi7r8Ev) | Include | Hardware compatibility and redundant-path sequencing |
| [Cloud Storage, October 8](https://status.cloud.google.com/incidents/mSFVt6PiP557bjRyYsut) | Include | Rollback completeness and recurrence |
| [europe-west2 power, October 20 UTC](https://status.cloud.google.com/incidents/Xs2XTHzAVC9YnafnPyzj) | Include | Temporary maintenance topology and shared controller logic |
| [Cooling, July 15](https://status.cloud.google.com/incidents/3BvH3LVGcupoYqV6F4Nw) | Defer | Redundancy theme overlaps the selected power example; an unresolved load discrepancy limits interpretation |
| [India latency, June 5](https://status.cloud.google.com/incidents/5fGQt4VbkDnr3Yp8PXPr) | Defer | Fire-triggered rerouting adds limited new change-review coverage; retain for a future resilience set |

The [machine-readable ledger](google-curation-review.json) maps all eight staged
source IDs to decisions, reasons and canonical IDs where included. Its revision
hashes identify the staged feed, not archived copies of HTML reports. A later
source correction requires another review and index rebuild. The ignored local
queue retains its pending-review status; the ledger records this curation work.

## Interpretation limits

Canonical caveats preserve revised timelines, differing product recovery windows,
expanded cluster scope and preliminary/final report differences. The October
power incident is an external trigger exposing a maintenance-dependent failure
condition, not evidence that maintenance caused the external fault. Selection
does not require every incident to have a deployment trigger.

These are historical external analogues, not successful-change outcomes, local
service incidents, current health, policy or permission to deploy. Provider
severity remains unextracted; prospective CRA2 risk remains unassigned. The
outage-heavy selection cannot estimate failure probability. CRA2's existing
at-most-one external result, meaningful-term filter, risk floors and freeze
verification safeguards remain in force.

## Validation

Local checks completed November 6, 2026 UTC (November 5 in the review timezone):

| Check | Result |
|---|---|
| Locked root environment | `uv sync --locked` succeeded |
| Root offline tests | 692 passed; four live tests deselected |
| Week 1 tests | 513 passed |
| Week 2 tests | 525 passed |
| Fast evaluation gate | 20 cases × five repeats; all 100 scored 10/10; all decision contexts repeatable; zero provider requests |
| Canonical validator | 19 records, 18 reports, one plan, nine companies; longest rendered summary 184 words |
| Existing local index | Rejected the changed corpus before rebuild |
| Cached model rebuild | 76 documents / 87 chunks; 46 local incident records and 19 external summaries; BGE-small-en-v1.5, 384 dimensions |
| Wheel | Canonical catalog bytes match; local staging and review ledger excluded |
| Diff | `git diff --check` passed |

Regression coverage includes duplicate exact source URLs, stale indexes after
additions, external relevance/cap boundaries, and 18 state-recovery cases (six
new reports × full/threshold/SAC). Source identity, facts, caveats and unassigned
risk survive recovery between tool calls without replacing policy or tool
observations. Three existing plan-validation tests now locate the plan by type
rather than assuming it is the last catalog entry; their rejection expectations
are unchanged.

The [real-encoder smoke results](google-curation-retrieval.json) retain all seven
chosen queries. VMware, network-maintenance and power queries returned their
new external examples; Vertex, router and storage queries ranked local chunks
above external candidates. The generic query returned no external source. No
ranking rule or relevance threshold was changed to favor these examples. This
is a small integration check, not a held-out recall measurement or proof of
causation. A source-incident-separated retrieval benchmark remains the next
quality step. No live Groq or Slack requests were used.

The test commands used the locked environments directly (`.venv/bin/python`
for root and `week2/.venv/bin/python` for Week 1/2), with `TMPDIR=/tmp` and
`PYTHONPATH=.` where needed. The `uv run` wrapper could not access its cache
inside the restricted environment; locked sync and the offline wheel build
used approved cache access. Historical evidence reports were left unchanged.
