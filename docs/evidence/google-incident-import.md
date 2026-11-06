# Google incident staging verification

Verified 2026-11-05 America/Chicago (2026-11-06 UTC). This increment follows the
merge of PRs #20, #21 and #22 into main. It adds a discovery and review-staging
path, with no automatic source promotion or retrieval/index changes.

## Gates

| Check | Result |
| --- | --- |
| Locked dependency synchronization | `uv sync --locked --offline` succeeded; no dependency changes |
| Root offline suite | 689 passed, 4 live-provider tests deselected |
| Week 1 suite | 508 passed, including three staging-to-retrieval boundary tests |
| Importer-focused regressions | 57 pure normalization/staging tests and 44 CLI/transport/file tests, included in the root total |
| Fast policy gate | 20 cases × 5 repeats = 100 assessments; minimum/mean 10/10; all 20 cases repeatable; zero provider attempts |
| Wheel | Offline build; packaged CLI ran outside the checkout, staged one synthetic fixture, and repeated unchanged; local staged data excluded |
| Actual public feed | Two explicit HTTPS requests; eight candidates staged; repeat returned unchanged; zero promotions |

Commands from the repository root:

```sh
uv sync --locked --offline
TMPDIR=/tmp PYTHONPATH=. .venv/bin/python -m pytest -q -m 'not live'
TMPDIR=/tmp PYTHONPATH=. week2/.venv/bin/python -m pytest -q week1/tests
PYTHONPATH=. .venv/bin/python scripts/run_evals.py --mode fast --repeat 5 \
  --require-repeatable --out /tmp/cra2-google-staging-evals-fast.md
PYTHONPATH=. .venv/bin/python -m cra2.import_google_incidents --fetch \
  --output data/.staging/google-incidents.json
```

Week 2 runtime code was unchanged. The boundary tests exercise existing policy
floors and freeze uncertainty while confirming that staged text cannot enter
retrieval. They use synthetic narratives, including an instruction-like string,
and a deterministic test encoder; they are not a retrieval-quality benchmark.

## Actual-source observations

The [machine-readable evidence](google-incident-staging.json) records source
IDs/revision hashes, checked times, counts, file hashes and the unchanged corpus
digest. It contains no narrative excerpts. The actual candidates remain in the
ignored local staging file, with mode `0600`; they are not in Git or the wheel.

- The repeat preserved staging bytes, inode and modification time.
- All five canonical JSON files and the SQLite retrieval index kept their hashes.
- The indexed corpus digest still matched the canonical source documents.
- All eight candidates remained `pending_review`, with risk unassigned.
- None of these eight source URLs matched the 13 curated records. The existing
  2025 Google incident remained in the reviewed catalog even though this feed
  response omitted it.
- Both requests went to the fixed public Google endpoint. No Groq or Slack calls
  were made. The feed snapshot is partial, not a complete historical archive.

## Review findings addressed

The implementation rejects malformed/oversized responses, duplicate JSON keys,
conflicting incident IDs, redirects, HTTP protocol errors, unsafe paths and
unrecognized existing outputs. It checks the read deadline after EOF as well as
between reads. Atomic publication uses a cooperative lock and content/identity
rechecks; it does not claim protection against a hostile local process that
ignores the lock and races the final filesystem operation.

Repeated update pointers do not double-count when they omit location metadata.
Edited update timestamps participate in freshness ordering separately from the
incident timestamp. Timestamp normalization is independent of platform-specific
year formatting. Older revisions cannot replace newer ones, and feed omissions
do not delete staged records. Canonical source matching uses URLs rather than
CRA2's descriptive IDs.

## Remaining work

Human source review and manual curation are required before any candidate enters
retrieval. There is no automatic approval, model-written summary, scheduled poll,
successful-change label, or risk-probability claim. Verified successful outcomes
and incident-level held-out relevance evaluation remain separate work. See the
[import and review guide](../google-incident-import.md).
