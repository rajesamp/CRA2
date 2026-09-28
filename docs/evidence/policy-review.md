# Advisory policy and credential review

Review date: 2026-09-28. Scope: the local CRA2 CLI/library, its packaged data,
provider boundary, active Markdown documentation, and evaluation runner.
Historical review/evaluation reports retain their original scope and results.

## Findings addressed

| Finding | Change | Verification |
|---|---|---|
| Route names implied approval or blocking authority | All risk bands now describe reviewer attention; rule prose suggests checks | Policy regression checks and updated 20-case calibration expectations |
| A catalog freeze alone forced high risk | Freeze context is explicitly unconfirmed, has zero score weight, and asks for verification | Paired assessment with/without a freeze keeps the same score and level |
| Missing or generic requests reached validation errors or scoring | Targeted clarification precedes context retrieval and scoring | No-context/no-provider regressions; null score, level, and route |
| Matching change type alone admitted unrelated foreign incidents | Cross-service retrieval requires at least two informative shared terms | Type-only rejection, copy-edit query, and bounded retrieval tests |
| Team policy had no effective precedence or conflict record | Explicit team values override request/catalog settings; false values also win | Positive/negative overrides, evidence-source checks, no-mutation tests, installed CLI checks |
| Credentials needed explicit output and diagnostic protection | Known-key guards cover inputs, results, model context, response metadata, cache, and reports; provider diagnostic logs are suppressed and exception chains detached | Fake sentinel tests over the real SDK with mocked HTTP, visible logging canary, provider error/echo tests, and configuration/report regressions |

The sample team policy flags `auth-service` as high risk, with a medium minimum.
It adds no new service or dependency. Dependency relationships still come only
from the explicit graph.

## Calibration changes and validation

The reviewed policy intentionally changes CHG-04 from high to medium and CHG-08
from high to low: removing the freeze penalty/floor yields scores 0.48 and 0.25,
respectively. Both retain the visible unconfirmed freeze and verification question.
All route expectations change to the new review labels. The other eighteen
expected levels stay unchanged. This is a recorded policy revision, not a claim
that the old and new policies have identical outputs.

The [policy evaluation](evals-policy-fast.md) records 100 offline assessments:
20 cases, five repeats each, all scoring 10/10 with identical decision context.
It includes data/policy hashes and the UTC run window. The full offline regression
suite and Python static checks pass. An isolated wheel installation verifies
bundled policy data, explicit team overrides, and clarification behavior outside
the checkout. CI additionally validates supported Python 3.10 and 3.13.

Independent review found two additional output gaps—clarification questions and
evaluation reports—and regression tests now cover both. Sentinel values are
fictional; tests never require the developer's actual credential.

## Evidence limits

- Known-key detection compares exact configured/SDK-held values. It does not
  guarantee detection of transformed or unknown secrets, inspect process memory,
  control external caller logging, or establish provider retention behavior.
- Clarification and incident relevance use deterministic lexical rules. They
  cannot prove semantic relevance, completeness, or truth of model prose.
- Team settings are local configuration, not an authenticated tenant boundary.
  Hosting, live freshness, ingress/egress policy, and postmortem ingestion remain
  open design work, described in the [FAQ](../faq.md).
- The calibration cases informed the rules. Unseen-change quality and production
  operational correctness remain unmeasured. This offline report makes no live
  Groq performance, price, repeatability, or Caveman savings claim.

Verdict: no remaining blocker found within the reviewed local implementation;
merge is contingent on the PR's CI checks passing.
