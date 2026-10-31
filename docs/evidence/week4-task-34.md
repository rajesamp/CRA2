# Week 4 selected local engineering close-out

2026-10-31. **Selected local scope verified.** Tasks 26–33 have named local
implementation/evidence; task 34's local launch and final rehearsal are verified
here. Original upstream task 34 remains partial for public deployment and
backup video, both outside the owner's selected local target. No human review,
independent teammate run or live-provider quality is inferred.

## Final fresh-process walkthrough

The [documented isolated launch](../local-demo-script.md) created fresh private
storage and started the current app on loopback port 7863. The normal/default
app and actual owner records were preserved. Two new browser sessions completed
the same five submissions: saved preference, unprompted recall with concrete
review, dependency miss/repeat hit, and greenlight refusal with continued review.
The dashboard was reached from chat through its existing demo gate.

[Actual final rehearsal record](week4-task-34.json): 21:08:30–21:10:32 UTC,
**122 seconds (2 min 2 s)**. This measures browser loads and automation handoffs,
not spoken narration. Private metadata independently contains five browser
records, three actual tool invocations and zero provider requests. Directory
0700 and file 0600 modes were verified for isolated memory/audit/telemetry.

[Final cache-hit screenshot](week4-final-cache-hit.jpg) ·
[Unprompted recall trace](week4-final-recall.txt) ·
[Final dashboard](week4-final-dashboard.jpg) ·
[Observed dashboard text](week4-final-dashboard.txt). Browser session B's
four requests show 0/3 tool failures, 3/6 tool-cache hits, 2/4 eligible preference
applications, 0/10 rail interventions and zero external model requests. The
small mixed-query time sample is not the dedicated cache benchmark or an SLA.

## Final checks

| Gate | Observed result |
|---|---|
| Week 2/3/4 integration suites | **277 passed**, 188.46 s |
| Root core, live tests excluded | **502 passed**, 4 excluded, 12.03 s |
| Unchanged Week 1 in Week 2 environment | **494 passed**, 16.84 s |
| Fast calibration, 20 cases × 5 repeats | **100/100**, zero provider attempts |
| Final original-case scorecard | **18/18**, zero provider attempts |
| Corrected reserved-label validation | **4/4**, zero provider attempts |
| Explicit fault demonstrations | **9/9**, zero provider attempts |
| Timed browser rehearsals | **137 s**, then fresh process **122 s** |

[Final original scorecard](week4-final-scorecard.json) and
[final corrected validation](week4-final-reserved-validation.json) were rerun
after task 32's late accounting/team-identity fixes. Original baseline, initial
reserved failures and label review remain unchanged. The final post-gate change
was documentation and the dashboard label “External model-request attempts,”
clarifying that local BGE work is separate; the final browser run verifies it.
[Raw final fast-calibration report](week4-final-calibration.md) is retained.
NeMo's vendor deprecation warning remains in test output.

## Evidence limits and handoff

- [Learning guide](../week3-week4-learning.md): components, alternatives and
  implications; every task also has an ignored private learner note.
- [Demo script](../local-demo-script.md): launch, reset with new storage,
  walkthrough and honest recorded-evidence fallback.
- [Task 30 comparison](week4-task-30.md): original 16/18→18/18 is application
  improvement; corrected reserved 4/4 is separate label validation. Same-author
  contract cases are not independent human-labeled quality gold.
- [Task 23 benchmark](week3-task-23.md): 30 samples per condition, warm graph
  p50 906.635→167.889 ms; bounded to that measured query/runtime.
- Snapshot freshness, active incidents and current freeze applicability remain
  unknown. Risk floors/preferences are not calibrated model risk ratings.
- No hosting, backup video, Slack posting or external telemetry export was
  performed. Prior Week 1 team/clone/sharing acceptance remains pending.
- Source/runtime/evidence commits are local; unrelated existing edits and
  historical evidence were preserved. No production-readiness claim is made.

The local demo was left running at `http://127.0.0.1:7863`, with the final
browser tab retained. Use documented launch instructions if a later process
restart is needed. Local final completion is distinct from original upstream
public deployment/video acceptance.
