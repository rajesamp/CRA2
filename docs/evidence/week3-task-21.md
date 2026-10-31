# Task 21 — refusal, continuation and unsupported evidence

2026-10-31. Two regression tests first failed: a concrete approval request
ended without review; unrelated TLS evidence reached the reviewer for a
payment-timeout question. The failing tests were committed before the fix.

The workflow now declines operational approval while continuing a sufficiently
detailed permitted review. A bounded timeout/retry coverage check prevents
model assessment when retrieved incident/runbook text lacks that mechanism.
Local mode can still show contextual passages and general review checks, with
an explicit unsupported-mechanism notice and no model risk rating.

Actual transcripts are in [week3-task-21.json](week3-task-21.json): bare approval,
concrete approval plus local review, payment timeout with actual mismatched
retrieval, and the same provider-boundary probe with a forbidden offline reviewer.
All four completed with zero provider attempts. The real local graph invoked
MCP and retrieved three passages for the concrete changes. The unsupported
provider-boundary case returned `insufficient_evidence` without invoking the
reviewer. The final copy was shortened to preserve the existing concise UI.

Verification: 14 focused support/useful-answer tests passed in 8.37 s after
fixes, including preservation of local retry-change facts and review checks.
The broader preceding focused run had 43 passes and one local-display regression;
that regression was fixed in code/copy, without changing existing tests.

Learning: citation membership proves that a source exists, not that its content
supports the conclusion. This explicit lexical coverage check detects the
observed mismatch; `not_disproven` is deliberately not named “supported.” It
does not establish entailment, causation or protection for every mechanism.
Week 4 must measure additional labeled cases and benign false positives.
