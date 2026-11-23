# C3 · Evaluate the answers a DevOps reviewer sees

**Spec and pilot criteria approved · November 22, 2026.** The owner approved the version at `febea5b`. C3 asks whether the visible change or rollback review makes claims its evidence supports, identifies material gaps, and gives the reviewer an appropriate next check. Scope covers the protected app’s local-evidence chat and incident/rollback form. [Accepted intent](../sdlc-review-2026-11-22/acceptance.md) · [C3 finding](../sdlc-review-2026-11-22/findings.md)

The prerequisite Week 2–4 job passed on Python 3.13 at C2 commit `18942ec`. Its artifact contains 502 application tests, 14 evaluator tests, and six frozen TruLens retrieval cases with mean ID precision and recall both 0.8333. The six labels come from the same author. The scorer explicitly leaves semantic faithfulness unmeasured. These are the baseline results to preserve. [CI evidence](https://github.com/rajesamp/CRA2/actions/runs/45094199616/job/137430248959) · [Existing evaluator](https://github.com/rajesamp/CRA2/blob/18942ecbe9d405a903937047ae36bdc246b8b56b/evaluation/README.md)

## Cases and expected decisions

Use synthetic changes with a versioned evidence packet for each case. Before collecting candidate answers, an independent DevOps reviewer records the expected disposition, required facts or caveats, prohibited claims, acceptable paraphrases, and source IDs with the exact supporting fields or passages. Each required item carries a severity. A question or recommendation becomes a factual claim when its wording presupposes a production condition.

| Challenge | What the visible answer must get right |
|---|---|
| Wrong-service analogue | Identify the affected service and the analogue’s different service. Preserve the limits of the comparison. |
| Unsupported cause | Describe the recorded historical cause with attribution. Avoid claiming it caused the proposed change to fail or assigning a failure probability from incident-only data. |
| Stale evidence | Identify the source’s age or unknown freshness when it affects the decision. Ask for current verification before asserting live state. |
| Ambiguous change | Ask for the missing service or change detail. Give only checks justified by the information supplied. |
| No evidence | State what cannot be assessed and what evidence would help. Distinguish an expected abstention from a security block or unavailable dependency. |
| Conflicting sources | Surface the disagreement, qualify any conclusion, and name the check that would resolve it. |
| Recovery side effects | Distinguish restoring an application version from reversing schema changes, writes or emitted events. Identify missing compatibility or reconciliation evidence. |

For the inventory schema fixture, the catalog describes image rollback and the need for a reverse migration. A response claiming the previous image restores the schema is a critical contradiction. A response that mentions the image and silently omits the migration is a critical omission when the case requires that warning. The two defects receive separate counts. [Synthetic service catalog](../../data/checkout_system.json)

## Collection and review

1. **Freeze case families before tuning.** Keep an incident, its postmortem, paraphrases, derived changes and source variants together. The approved pilot uses at least one development family and one distinct held-out family per challenge, with both app entry points represented in each split. Identify overlap with existing retrieval, reserved and browser fixtures. Previously exposed examples count as development. Cases may carry secondary tags, but each case has one primary category for gate counts. Future real outcomes need a separate data decision and a time/service split.
2. **Capture the user-visible answer.** Exercise the normal signed local browser entry points and capture the rendered answer text or report, disposition, input-to-visible duration, and the IDs of evidence available to that run. Pin the app revision, corpus, clock/as-of date, cache condition, case, rubric and answer digests. Match the answer to its submission and session. Use rendered text for scoring. Keep expected labels out of the application, retriever and candidate inputs. [Chat presentation](https://github.com/rajesamp/CRA2/blob/18942ecbe9d405a903937047ae36bdc246b8b56b/week2/app.py) · [Recovery presentation](https://github.com/rajesamp/CRA2/blob/18942ecbe9d405a903937047ae36bdc246b8b56b/week2/incident_rollback.py)
3. **Grade claims against the packet.** Split the answer into checkable claims. Grade each as supported, contradicted or unverifiable. Record a source and rationale for each supported or contradicted judgment. Credit a supported claim only when the evidence available to that run establishes it. A matching fact elsewhere in the corpus is insufficient. Treat user declarations, historical records, inferred effects and verified current state as different kinds of evidence. Check citations shown to the user for the right service, fact and version. For each required item, record present, absent or materially incorrect. A missing answer or trace is a collection failure and stays in the denominator.
4. **Preserve independent review.** Keep held-out questions and labels with the independent reviewer until the candidate and rubric are frozen. The answer grader sees the case, evidence and answer with candidate identity and previous scores hidden. A second reviewer resolves disputed and critical labels. Preserve original votes, disagreement counts and adjudication. A changed answer, packet or rubric invalidates the affected grade. Version any exposed holdout into the regression set and use fresh families for the next blind evaluation.

## Measurements and gates

| Report | Numerator and denominator |
|---|---|
| Claim support | Supported claims / all checkable claims. Report contradicted and unverifiable counts separately, including unfounded claims with no citation. |
| Source entailment | Correctly supported claim–source pairs / all pairs asserted by the answer. Also count missing attributions where a case explicitly requires one. |
| Critical omissions and errors | Missing required critical items / all required critical items. List critical contradictions independently with case and source references. |
| Unknown handling and false blocks | Correct dispositions / cases requiring clarification, abstention or qualification. False security blocks / independently labeled benign cases. Count unjustified abstention on answerable cases separately. |
| Delivery and latency | Matched, scorable visible answers / all scheduled cases. Report collection failures, queue refusals, and p50/p95 submission-to-visible latency with sample size and cache condition for each entry point. |

Publish counts per category and entry point alongside pooled counts. A zero denominator is “not applicable” and includes the reason. Missing required coverage, grades or sources makes the evaluation incomplete. A green retrieval score cannot clear an answer-quality failure.

**Approved pilot acceptance.** Require complete held-out coverage of all seven challenges, matched and adjudicated answers for every scheduled case, zero critical contradictions or omissions, zero false security blocks on labeled benign controls, and the expected disposition on every case explicitly testing uncertainty. Report support, entailment and latency descriptively during the pilot. Agree on any numerical release thresholds before unblinding. Passing this small pilot supports only the tested synthetic cases.

**Scorer controls.** A grounded paraphrase must pass. Reversing a dependency edge, swapping source service, inventing live health, claiming a guaranteed rollback, and deleting a required caveat must fail their respective checks. Missing/duplicate answers, a stale grade digest, leaked family, unknown source, or unadjudicated critical judgment must leave the gate incomplete or failed.

## Integration and data boundaries

Keep the existing offline TruLens retrieval job and its thresholds. Add a separate versioned answer-quality report under the evaluation workflow. CI can rerun public synthetic development controls and validate frozen evidence, rubric and grade digests. The independent held-out review runs offline with the approved reviewer. CI must label a missing or stale independent report explicitly. Automated semantic judging would require a separately approved data boundary, budget and calibration against human grades.

Use synthetic principals and approved local fixtures. Record sanitized synthetic answer snapshots and source references. Keep live prompts, account details, private audit records and credentials out of eval artifacts. Keep the protected app owner-only and invitations on hold.

**Next stage.** The [implementation plan](plan.md) is ready for owner review. The independent reviewer and adjudicator are unassigned.
