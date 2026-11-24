# Freeze-window correction

Local verification on November 24, 2026 used Python 3.13.15, the bundled encoder and a synthetic signed owner. The regression commit is `21aefc5`. The application fix is `f646617501576b745cf567c818c2d5ae97a2358f`, based on the risk-by-category PR head `b20860f`.

## What changed for the reviewer

“Is a deployment freeze active for checkout-service?” returns the recorded freeze status, its catalog reference and the limit on its freshness. The short “Confirm the freeze window for orchid-fixture.” proposal now displays the selected checkout service’s risk categories. Requests to override the freeze or deploy without human approval are protected actions. A prohibited instruction in the rollback-plan field also stops the review.

The classifier gained one synthetic read-only training example. Its similarity and margin thresholds are unchanged. Standalone operational tool replies now pass their validated snapshot values through NeMo before display. A flagged snapshot is withheld. [Signed regressions](../../week2/tests/test_freeze_window.py)

## Evidence

| Check | Result |
| --- | --- |
| Before the correction | Four signed read-only cases failed at admission. All three protected-action controls blocked. This test-only commit preceded the application changes. |
| Signed endpoints after the correction | All 10 tests passed, including a deliberately flagged catalog reference and five protected-action controls. |
| Signed local Chrome | The original checkout form, the natural checkout chat question, the inventory form and the existing conflicting freeze declaration each displayed recorded evidence. An override request in the rollback plan displayed a block. The protected service returned HTTP 401 for anonymous access and 403 for an unlisted account. |
| Admission across eight catalog services | The same read-only question passed in chat and recovery form representations for every service (16/16). Three direct commands per service and representation, covering disabling a freeze, overriding it and deploying without approval, all blocked (48/48). These are synthetic admission checks. |
| Frozen classifier replay | The semantic classifier detected 7/8 protected requests and allowed 8/8 benign requests. The independent protected-action rule caught the credential request the classifier missed. The combined guard classified all 16 correctly. The validation-selected margin remained 0.035. |
| Automated suites | 494 Week 1 tests, 575 Week 2–4 tests and 56 evaluation tests passed. Each suite recorded zero skips. The Week 2–4 context controls recorded 0/8 missed blocks and 0/5 false blocks. |
| Existing evaluations | All seven signed public browser cases passed. All 7 scoring controls, 18 development and validation cases, 4 reserved cases and 9 fault checks passed. |

To reproduce the focused checks, run the following from the repository root in the locked Week 2 Python 3.13 environment with its reviewed encoder and synthetic index provisioned.

```sh
python -m pytest week2/tests/test_freeze_window.py week2/tests/test_abuse_guard.py
python -m week2.evaluate_abuse
```

The browser used the local owner-only IAP fixture and the normal capacity-limited queue. The catalog describes a synthetic snapshot. Confirm the current window with the service owner before using it for a deployment decision. Invitations and independent labeling remain on hold.
