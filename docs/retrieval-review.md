# Reviewing and freezing retrieval scenarios

The next step after the nine-case baseline is independent relevance labeling.
`evals/retrieval-review-queue.json` provides 18 **assistant-authored synthetic**
requests across five CRA2 services. They are proposed scenarios, not actual
customer change tickets or approved corporate labels. Six start in development
and twelve in evaluation; all reviews are empty. No new quality score is claimed.

## Review procedure

Two people should first review each request separately, without consulting model
rankings or one another's judgments. Use `data/public_evidence.json` and its
linked first-party sources. Record each judgment in the case's `reviews` list:

```json
{"reviewer": "reviewer-id", "source_ids": null, "reason": "Insufficient detail to select an analogue."}
```

Use a stable reviewer identifier and a reason for every judgment. `source_ids`
means:

- `null`: uncertain, ambiguous or unable to judge. This is never a negative label.
- `[]`: the reviewer finds no justified external analogue in the current catalog.
- `["public-..."]`: one designated relevant source ID from the canonical catalog.

The current evaluator measures one designated target per case, not exhaustive
relevance. If several analogues seem equally suitable, use `null` and refine the
case or agree a designated target with a documented reason before freezing.
Reviewer identifiers are self-reported metadata. The tool checks distinct names
but cannot authenticate people or establish actual independence. Do not enter
fabricated reviews to make the queue pass.

Validate the queue without exporting it:

```sh
PYTHONPATH=. .venv/bin/python scripts/review_retrieval.py evals/retrieval-review-queue.json
```

Two matching, non-null judgments make a case agreed. Missing reviews remain
pending; differing judgments are conflicts; null judgments are ambiguous.
Resolve disagreements through further source review and retain the discussion
in the PR and revised reasons. Do not silently remove difficult cases. If agreed
labels expose a source incident on both sides of the split, move all scenarios
for that incident together before freezing. The split is by official source URL,
not chunk ID. There is no automatic partition repair.

## Freeze and evaluate

Once **every** case has two distinct, agreeing reviewers, export a new bundle:

```sh
PYTHONPATH=. .venv/bin/python scripts/review_retrieval.py evals/retrieval-review-queue.json \
  --freeze /tmp/cra2-reviewed-retrieval.json
PYTHONPATH=. week2/.venv/bin/python scripts/evaluate_retrieval.py \
  --review-bundle /tmp/cra2-reviewed-retrieval.json --out /tmp/cra2-reviewed-results.json
```

Export refuses pending, uncertain or conflicting labels and never overwrites an
existing output. The single bundle includes the review packet, derived evaluation
cases, packet checksum and canonical public-corpus checksum. Evaluation recomputes
all of these before searching. A modified bundle or changed source catalog fails
validation. Hashes detect inconsistency, not malicious rewriting of all fields;
Git review history is still needed for accountability. The existing index also
checks its corpus and model fingerprints.

`--cases` preserves the original lightweight benchmark workflow; it does not
claim independent review. It is mutually exclusive with `--review-bundle`.
Reports record which path was used and the input checksum. The original nine-case
baseline and historical evidence remain intact.

## Limits and next action

No production ranking, risk rules, source corpus, tool execution or model settings
change in this increment. No reviewers are contacted automatically, and the new
queue is not evaluated until its labels are agreed. After review, freeze the
labels before the first evaluation and tune only on development cases. Published
results or assistant-authored scenarios should not be described as a blind
holdout. Broader, independently collected real change requests remain necessary
before drawing production-quality conclusions.
