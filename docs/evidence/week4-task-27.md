# Task 27 — frozen local evaluation harness

2026-10-31. One command from repository root:

```sh
TMPDIR=/tmp week2/.venv/bin/python -m week4.evaluate --out /tmp/cra2-local-evaluation.json
```

The harness reuses the six source-contract walkthrough rows and adds 12
explicit development/validation cases. Four reserved sanity cases are executed
only with `--split reserved` after choices freeze. IDs, inputs, expected labels
and splits live in `week4/cases.json`; scorer and data/source hashes accompany
each report. Provider access is forbidden, including the unsupported-evidence
probe in Groq mode: its reviewer is an explicit forbidden offline adapter.

Checks cover expected routing, explicit approval refusal, the observed
unsupported-mechanism boundary, a synthetic context injection, actual MCP
deadline, absent evidence, benign help, ambiguous/unknown service and exact
numeric display. The checkout source contract additionally requires the
known directly relevant CX-101 source within its top three passages. This
label follows the recorded fictional 4 s→400 ms postmortem, not a new model
judgment. One labeled retrieval example is not general relevance accuracy.

Verification: three scorer/manifest tests passed; the known failing canary
returned exit status 1 and printed `Known failing canary detected: True`.
The runner similarly exits nonzero for any ordinary case failure, not merely
writing a reassuring report. The baseline is task 28 and has not been improved
or tuned in this task.

Learning: a scorecard is only as strong as its cases and labels. These labels
come from accepted contracts and explicit synthetic controls. Reserved cases
are same-author sanity checks, not independent human-labeled quality gold.
No live model-quality, factual-entailment or production-accuracy claim follows.
Cases inspected during error analysis become regression evidence.
