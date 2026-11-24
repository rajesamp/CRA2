# Risk by category verification

**Passed locally on Python 3.13.15, November 23, 2026.** Tested source `c07d2af048da1d24d9535604b14593f79e1ba131` on `codex/v2-review-signal-specs`. The source and dataset identity check produced bundle `CRA2-fd88fc0bf8cf`. The first regression in `4515848` failed on the absence of the category section before implementation. [Implementation plan](risk-categories-plan.md)

| Local check | Result |
|---|---|
| Week 2–4 non-live tests | 562 passed, zero skipped or failed. |
| Evaluation tests | 14 scoring tests and 42 answer-quality tests passed. All 19 public controls matched. |
| Context guardrails and queue | Zero missed blocks in 8 controls and zero false blocks in 5 benign controls. All 11 required capacity cases passed. |
| Evaluation scenarios | 7 scorer controls, 18 development and validation cases, 4 reserved cases and 9 fault checks passed. The scenario and fault runs recorded zero provider attempts. |
| Offline retrieval | TruLens passed on 6 frozen cases. Mean precision and recall were both 0.8333. The guarded callback probe recorded 7 public inputs. |
| Evidence and safeguards | The checkout fixture showed technical and operational citations plus two explicit gaps. Tests covered changed and removed sources, review and category mismatches, conflicts, escaping, guardrail receipts and the audit-write failure path. |

Two isolated Chrome sessions used the same signed synthetic owner identity on the loopback server. Editing any of the seven form fields cleared the result. Returning to the original text did not revive it. A delayed earlier delivery could not replace a newer review. A blocked review and loss of sign-in each cleared the displayed findings. The local capacity mount delivered all four cards through the queue. The anonymous intro and sign-in redirect exposed zero seeded findings or private markers. The protected mount denied anonymous and unlisted accounts. [Browser verification](../../evaluation/probe_risk_categories_browser.py)

An exploratory short freeze-window query was blocked by the existing admission classifier before category generation. The signed positive cases used complete checkout and inventory change proposals. The guardrail counts above describe their fixed controls.

Verification used local fixtures and the locked Python environments. Hosted CI, a Cloud Run rollout and independent grading are separate release steps. Owner-only access and the invitation and independent-labeling holds continue.
