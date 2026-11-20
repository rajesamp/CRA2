# Offline retrieval evaluation

TruLens Feedback 2.16.0 runs in its own locked Python 3.13 environment, outside
the application and container dependencies. It computes document-ID precision
and recall for six frozen source-grounded fictional change scenarios.

```sh
uv sync --locked --project evaluation --python 3.13
week2/.venv/bin/python -m evaluation.collect --out /tmp/cra2-retrieval-ids.json
evaluation/.venv/bin/python -m pytest evaluation/test_score.py -q
evaluation/.venv/bin/python -m evaluation.score --input /tmp/cra2-retrieval-ids.json --out /tmp/cra2-trulens.json
```

The collector uses the same checksum-verified BGE encoder and local index as
the application. Provision them with the existing Week 1 setup first. It exports
only synthetic case IDs, distinct retrieved document IDs and provenance hashes;
no live questions, identity, private audit or retrieved passage text is read.
The first three chunks are stably deduplicated to document IDs. Denominators
report the actual distinct documents and the two reference documents per case.

Labels and minimum regression floors are frozen in `retrieval-cases-v1.json`.
They require at least one of the two mechanism-specific sources for each case,
mean recall >= 0.5 and mean precision >= 1/3. They are same-author regression
labels, not independent human gold or production quality targets. Source drift
requires a reviewed new label version; do not relabel to match retrieved output.

Empty retrieval/reference, duplicate IDs, absent/duplicate cases, nonfinite or
out-of-range metrics, and attempted egress fail the gate. Perfect, partial,
irrelevant and malformed fixtures test scorer behavior. CI runs this alongside
the existing Week 2–4 security contracts and fault controls.

`GroundTruthAgreement` normally selects an LLM provider when none is supplied.
This adapter explicitly supplies a provider that raises on invocation. A Python
audit hook blocks internet socket/DNS operations before importing the framework;
attempt counters also fail the run if a library swallows the exception. This is
a Python runtime control, not an OS network sandbox. No model API key is needed.

These scores do **not** measure answer faithfulness, semantic relevance, safety,
or jailbreak resistance. A future semantic evaluation needs an independently
labeled answer set, calibrated judge, approved data boundary and cost budget.

Both [Ragas](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/)
and [TruLens](https://www.trulens.org/reference/trulens/feedback/groundtruth/)
support offline retrieval metrics. The pinned decision and six shared API
fixtures are in `intent/guardrail-activity-evals/`. TruLens is a suitable pilot;
a quality winner is not established. The smallest separating test is both
adapters against the same frozen CRA2 corpus cases with identical failure rules.
