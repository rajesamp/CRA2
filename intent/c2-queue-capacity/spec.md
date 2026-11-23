# C2 · Queue and capacity limits for CRA2 reviews

**Draft for owner review · 2026-11-22.** This spec covers admission to chat and
incident/rollback reviews in the protected app. The public intro stays separate.
The draft follows the [accepted intent](../sdlc-review-2026-11-22/acceptance.md)
and [C2 finding](../sdlc-review-2026-11-22/findings.md). The prerequisite
[Python 3.13 CI job](https://github.com/rajesamp/CRA2/actions/runs/45067503651/job/137346837592)
passed on C1 head `21144ac`.

## Requirements

**Starting point.** The candidate app has an unbounded Gradio pending queue,
default callback concurrency of one, several chat submit/retry bindings, a
separate recovery callback and direct API handling enabled. These bindings can
represent the same logical review. The recorded Cloud Run configuration has one
maximum instance and HTTP concurrency four. Streams, heartbeats and submissions
can each occupy HTTP capacity. [Queue observation](../sdlc-review-2026-11-22/queue-probe.json) ·
[Cloud snapshot](../sdlc-review-2026-11-22/live-baseline.json) ·
[App bindings](../../week2/app.py)

The following values define a **provisional local test profile**. They make
boundary cases reproducible. Production limits and service targets need owner review.

| Limit | Test value | What counts |
|---|---:|---|
| Running reviews | 1 total across chat and recovery | From dispatch until the worker actually stops |
| Waiting reviews | 2 total across both operations | Accepted, awaiting dispatch |
| Outstanding per verified principal | 2 | Running plus waiting, across that principal's tabs and sessions |
| Admissions per verified principal | 4 per rolling 60 seconds | Each distinct accepted review once, including one later cancelled |
| Deadlines | 15 seconds waiting, 45 seconds running | Separate timers; enforce upstream timeouts within the remaining execution budget |
| Open long-lived connections | 2 per test instance | Count queue streams and heartbeats together; replacement connections respect the same bound |

1. **Bound admission before expensive work.** One logical submission reserves
   capacity once. Apply the same accounting to UI submissions, retry handlers
   and supported direct calls. Validate the verified principal, session and
   operation first. Reject a full queue before retaining the review body,
   classifying it, reading evidence or invoking tools. Work that proceeds still
   passes the existing abuse, NeMo and output checks.
2. **Give callers an actionable busy result.** A principal at its quota receives
   HTTP 429; shared saturation or unavailable capacity accounting returns 503.
   Provide a bounded `Retry-After` hint and a visible message that preserves the
   user's draft. Apply the equivalent status through the Gradio event protocol
   after a stream has started. Capacity refusals produce neither a risk assessment
   nor a security strike. Authentication and authorization retain their existing
   responses.
3. **Bound the whole review lifecycle.** Dispatch waiting work in arrival order
   among eligible requests. Expired waiting work cannot start. Cancellation,
   exceptions, deadlines, browser disconnects and normal completion release
   reservations exactly once. An expired running request suppresses late output;
   a still-running worker continues to occupy its slot. Reconnecting to a
   session-owned event must not submit or charge for a second review. A user
   can explicitly submit the same text again as a new review.
4. **Enforce isolation and recover after restart.** Derive the quota key from
   the verified principal. Bind event handles to the principal and session.
   Persist rate history and active security cooldowns across restart; reclaim
   orphan reservations safely. Before enabling additional instances, demonstrate
   that two workers sharing the same limits cannot exceed them or clear a
   cooldown early.

## Design

At the [authenticated mount](../../week2/cloud_app.py), extend the
[session boundary](../../week2/session_boundary.py) to identify work-bearing
events from the mounted callback inventory. Bind the queue join and handler
dispatch to one server-owned reservation. A supported direct heavy call must
acquire the same reservation before its callback runs. Reject an unclassified
work-bearing route before admitting it. Set a finite Gradio queue limit and
share execution capacity between chat and recovery. Count only heavyweight
review work against the review quota. Keep cancellation and status accessible
under load; independently bound stream connections, idle duration and
reconnections so idle tabs cannot consume unbounded resources.

Use atomic operations for reserve, start and finish. Store opaque reservation
IDs, principal-scoped quota keys, states and expiry times. Use conditional
updates so a late completion cannot release a newer reservation. Keep prompts,
source text and emails out of capacity records. A local clock-controlled
implementation must support the same lifecycle tests as durable accounting.
The [security cooldown](../../week2/abuse.py) remains a distinct control.
[Presence](../../week2/presence.py) reports recent activity on an instance and
does not supply the count of reviews in progress.

**Acceptance evidence**

| Test | Required observation |
|---|---|
| Saturation and fairness | Hold one worker, then admit two waiting jobs from eligible synthetic principals. The next globally over-limit submission receives the shared busy result. Independently hit the per-principal outstanding and rate ceilings across browser and direct paths. Observe zero excess starts and zero downstream calls for refused work. |
| Recovery and isolation | Use a controlled clock to race cancellation, expiry and completion. Exercise a reconnect, a hard restart and two worker processes. Verify one charge per accepted review, bounded reclaim, preserved cooldowns, owner/session isolation, and admission of the next eligible request. |
| Browser behavior | Exercise chat and recovery, an idle tab, a second tab and repeated reconnects through the mounted UI. At the connection ceiling, verify that a third stream consumes no review slot and displays a bounded retry. Check that busy feedback preserves input and that the owner can still cancel or read status. Include open queue streams, heartbeats and platform-level timeouts in the results. |
| Load and cost | Declare the workload before running it. Start with a local 10-minute mixed run, one submission every 15 seconds, alternating chat/recovery and two synthetic identities. Test bursts separately. Record offered, admitted, completed, refused, expired, cancelled and failed counts; maximum running and pending work; p50/p95 queue wait and end-to-end latency; and sample sizes. Separate expected overload responses from unexpected errors. |

Drain the queue at the end of each run. Every offered logical submission must
have one admission decision, every admitted review one terminal outcome, and
running and pending counts must return to zero. Missing counters or dropped
samples leave the load result inconclusive.

For any later capacity claim, measure cold and warm runs from submission
through visible result, and identify IAP/platform time separately from app
time. Tie request volume, busy/idle billed time, storage, networking, logging
and the public intro to the measured revision. Report registered accounts,
daily active reviewers, peak arrivals and concurrent work separately.
[Existing cost assumptions and measurement gaps](../../docs/cloud-run-budget.md)

## Policy conformance

The protected service stays owner-only and invitations stay on hold. This spec
authorizes no live load, new shared store, IAM change, increase in instance
count or rollout. Load tests use synthetic identities and local evidence.
Capacity counters are aggregate; session guardrail activity and the private
audit retain their existing boundaries. [C1 contract](../sdlc-review-2026-11-22/spec.md)

## Flagged concerns

- **Owner decision before implementation:** accept or revise the local fixture
  limits, the queue and execution deadlines, and the retry experience.
- **Before a service-level or user-count claim:** agree on the target workload
  mix and peak arrival rate, p95 wait and end-to-end targets, unexpected-error
  ceiling and total monthly budget. The earlier USD 10 figure is a planning
  assumption. The short local run cannot establish capacity for 1,000 users.
- **Before durable integration or scale-out:** identify the approved private
  storage boundary, retention period and atomic reservation mechanism. Verify
  that restart and two-process tests pass under contention and that the cost
  fits the approved budget.
