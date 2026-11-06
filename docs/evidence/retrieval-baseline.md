# Source-separated retrieval baseline

This increment adds an offline evaluation runner and nine assistant-authored
scenarios in `evals/retrieval-cases.json`. Two positive development cases cover
Google router/storage incidents; four evaluation cases cover Cloudflare,
Atlassian, GitHub and Meta incidents. Three negative cases cover generic or
insufficient content overlap. Every positive case has one designated analogue;
these are not exhaustive relevance judgments. Rationale is recorded separately
and never sent to retrieval.

Splits are assigned by canonical source URL before execution. Cases referring to
one incident cannot cross partitions, even if they would retrieve different
chunks. All source documents remain searchable: this evaluates retrieval, not
prediction on unseen source documents. Duplicate cases, missing labels, unknown
sources and cross-split source overlap fail validation.

The checked-in JSON records case and corpus hashes, the actual encoder
fingerprint, all returned chunk identities and scores, target rank, and per-split
metrics. Every positive case contributes to the denominator, including misses.
Negative cases have a separate false-positive accounting. Violations of the
three-result cap, one-external cap, canonical public provenance or local service
scope fail evaluation rather than becoming a quality score.

## Observed result

The cached BGE-small-en-v1.5 baseline retrieved the designated analogue at rank
one for both development cases and all four evaluation cases. All three negative
cases returned no external source. No provider requests or ranking changes were
made. See [complete results](retrieval-baseline.json).

These small, mechanism-specific queries were authored with knowledge of the
reports. They are source-separated but are **not blind held-out evaluation**.
Their perfect target-hit rate does not establish production accuracy or replace
the prior curation smoke results, which retrieved new sources in only three of
six differently worded queries. Neither result estimates risk or causation.

## Reproduce

From the repository root with the locked Week 2 environment and pinned local
model already provisioned:

```sh
PYTHONPATH=. week2/.venv/bin/python -m week1.setup_index
PYTHONPATH=. week2/.venv/bin/python scripts/evaluate_retrieval.py \
  --out /tmp/cra2-retrieval-baseline.json
TMPDIR=/tmp .venv/bin/python -m pytest -q tests/test_retrieval_evaluation.py
```

The runner uses the existing local index and fails if it is stale. It does not
fetch data, download models or alter ranking. Quality scores are measurements,
not a new pass threshold. Automated regression tests check accounting and input
boundaries using injected retrieval results, without downloading embeddings.

Next: have reviewers independently label realistic change requests (including
ambiguous and nonmatching requests), freeze a larger source-grouped evaluation
set, and tune only on development cases. The published evaluation scenarios
must not be reused as an untouched holdout after tuning against their results.
