# Task 33 — script and actual timed rehearsal

2026-10-31. [Demo script](../local-demo-script.md) budgets five minutes for Raj
Sam's local walkthrough. [Measured rehearsal](week4-task-33.json) ran from
21:03:09 to 21:05:26 UTC: **137 seconds (2 min 17 s)**. This times the actual
browser workflow including reload/readiness and automation handoffs; no spoken
narration was timed. Package installation and initial process creation were
outside that window.

Actual five submissions across two fresh browser sessions:

1. Session A saved the explicit high-risk checkout preference.
2. Fresh session B reviewed 4 s→400 ms without preference restatement.
3. Payment-dependents lookup missed, then the identical repeat hit.
4. “Greenlight this change” was explicitly refused while permitted review continued.
5. Dashboard was opened from chat through the existing demo gate and refreshed.

The list groups the two identical dependency submissions into one beat; total
submitted messages were five. [Memory screenshot](week4-rehearsal-memory.jpg),
[refusal screenshot](week4-rehearsal-refusal.jpg),
[actual recall trace](week4-rehearsal-recall.txt), and
[dashboard screenshot](week4-rehearsal-dashboard.jpg) preserve observed results.
The dashboard showed four B-session requests, three actual tool invocations,
3/6 tool-cache hits and 2/4 eligible reads applying the remembered preference.
Private compact telemetry independently retained five browser request records
across A/B and zero provider attempts. It contains no question/answer text.

The demo uses a fresh isolated private storage directory and leaves the normal
app/default memory and actual owner records untouched. A final fresh-process
rehearsal and documented local package remain task 34.

Learning: rehearsal proves the parts connect in the UI, including new-session
recall and honest cache status. It does not turn a local contract score into
live-model accuracy or a localhost URL into a public deployment.
