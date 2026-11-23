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

## C3 public answer-quality controls

Run the public calibration on Python 3.13 from the repository root.

```sh
evaluation/.venv/bin/python -m pytest evaluation/test_answer_quality.py -q
evaluation/.venv/bin/python -m evaluation.answer_quality \
  --verify intent/c3-answer-quality/public-development-evidence.json \
  --out /tmp/cra2-c3-public.json
```

The [public input packet](../evals/answer-quality/development-v1.json) includes four chat prompts and three recovery forms. Each case identifies its previously exposed development family, as-of date and synthetic evidence. Source locators resolve to versioned catalog fields, historical incident fields or that case's own operator declaration. An explicit empty evidence list is valid. A missing trace, unresolved source, future-dated incident or cross-case declaration invalidates a packet.

The [development key](../evals/answer-quality/development-key-v1.json) contains a small vocabulary of complete English statements, acceptable paraphrases, the expected disposition and required facts or caveats. The [control answers](../evals/answer-quality/development-controls-v1.json) supply seven grounded responses and twelve deliberate defects. Runner inputs contain neither answers nor keys. Only the offline scorer reads them together.

For these constructed answers, line one expresses a disposition. Each remaining line is one complete statement with optional bracketed citations. The scorer matches the entire statement against the public vocabulary. It checks each claimed source against the resolved evidence admitted for that case. An unrecognized statement or an altered answer, case, evidence value or rubric invalidates the grade binding. The scorer counts a contradicted required fact separately from an omitted one. An unverifiable claim earns zero support. A request for additional evidence is guidance and contributes no factual claim to the support denominator.

The [public report](../intent/c3-answer-quality/public-development-evidence.json) lists the actual findings per control and gives integer counts pooled, by challenge and by entry point. Repeated variants are counted separately. A public pass means the grounded answers and planted defects produced their expected findings. The constructed-answer report has zero browser-delivery samples. The separate signed-browser report below measures delivery and records the source fields used in each public case. Free-form candidate answers require grading under the approved rubric.

The independent pilot stays **incomplete** until the owner names a reviewer and adjudicator and their offline handoffs are complete. This command accepts public fixtures only. Keep independent inputs, answer keys, identities and votes outside this directory and CI.

### What the app returned locally

With the synthetic index provisioned, run the seven inputs through the same guarded callbacks that serve the UI.

```sh
week2/.venv/bin/python -m evaluation.probe_public_inputs --out /tmp/cra2-c3-callbacks.json
```

This probe reads only the runnable packet. It uses temporary local audit and memory stores, disables NeMo usage telemetry and model calls, and checks for network attempts in the probe process. It fixes the recovery analysis date at the case's as-of date. The artifact records application status, admission outcome and a digest of the returned text or HTML. An `ok` recovery status means the callback returned a report. Its factual support still needs review.

In the pre-fix callback run on Python 3.13.15, all four chat inputs passed admission and then routed out of scope. Of the three recovery forms, two returned reports and the inventory schema form hit the admission classifier's `prohibited_action_similarity` condition. The baseline preserves the original misses for comparison with the signed browser run below. [Callback observations](../intent/c3-answer-quality/public-callback-observations.json)

**Development family exposure.** The CX-104 TLS, CX-107 index and inventory schema families overlap the public retrieval cases and their incident/postmortem pairs. The health and freeze cases reuse the public catalog and the freeze/health verification runbook. The ambiguous-limit and unlisted-worker prompts are public from this version. Reserve each family and its derivatives for development in future blind runs. [Retrieval cases](retrieval-cases-v1.json) · [Public runbook](../week1/corpus/rb-freeze-health-verification.md)

### Reproduce signed local browser verification

Use the Week 2 Python 3.13 environment with the synthetic index, Node, Playwright and Chrome installed. For a shared Playwright installation, set `CRA2_PLAYWRIGHT_MODULE` to its module path.

```sh
week2/.venv/bin/python -m evaluation.collect_answers --out /tmp/cra2-c3-signed-browser.json
```

The fixture mounts the protected app on loopback with ephemeral signing keys, one synthetic owner and temporary storage. Each public input is submitted through a fresh browser context, paced to respect the normal owner quota. The driver captures the visible assistant message or recovery report. The collector matches its submitted values, delivery receipt, session, principal, queue event and callback before checking the visible facts and the source fields that the callback used. The report retains the submitted case ID, returned text, source references and duration. Signing credentials and browser session handles stay in the fixture.

On Python 3.13.15, candidate `ec84d8c` passed all seven exposed development cases with zero unmatched callbacks. The unsigned request returned HTTP 401 and the signed uninvited fixture account received HTTP 403. [Signed browser evidence](../intent/c3-answer-quality/public-signed-browser.json)

A passing run covers the seven exposed development cases. Independent labeling still requires the owner's named reviewer and adjudicator. The earlier callback-only observations are the pre-fix baseline.
