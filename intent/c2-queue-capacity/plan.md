# C2 implementation plan · Bound review work at admission and dispatch

**Approved for local testing · 2026-11-22.** The owner accepted the [C2 spec](spec.md)
at `5ea45a3ae94a61ef48f1b3e182476fb8f925fcf9` and its limits **for local testing**.
The owner approved the reviewed plan at `8e38a2d`, including the stream timings
in step 5, and requested 20 evidence-backed change reviews and 20 rollback
reviews checked in the submitting browsers. The protected app stays owner-only
and invitations remain on hold.

| Approved local limit | Enforcement point |
|---|---|
| 1 running and 2 waiting, shared by chat and recovery | Atomic admission and dispatch. The worker holds its slot until it stops |
| 2 outstanding per verified principal | Running plus waiting across tabs, sessions and supported HTTP entry points |
| 4 admissions per rolling 60 seconds per principal | Charge each accepted logical review once, including one later cancelled |
| 15 seconds waiting and 45 seconds running | Separate clocks from acceptance and actual dispatch, respectively |
| 2 open long-lived connections per test instance | Queue-data streams and heartbeats combined. Status and cancellation remain accessible |

## Files that change

| Files | Work |
|---|---|
| `week2/capacity.py` (new) | Local limits, atomic reservation transitions, persistent rate/cooldown expiry and bounded connection accounting. |
| [week2/cloud_app.py](../../week2/cloud_app.py), [week2/session_boundary.py](../../week2/session_boundary.py) | Inject the capacity service into the local test mount. Resolve verified principal, session, actual callback and event ownership before admission. |
| [week2/app.py](../../week2/app.py), [week2/responses.json](../../week2/responses.json) | Connect submit, retry and recovery to shared admission. Preserve input and explain when the queue is full, a wait expires or capacity checks are unavailable. |
| [week2/abuse.py](../../week2/abuse.py), [week2/workflow.py](../../week2/workflow.py), [week2/mcp_client.py](../../week2/mcp_client.py), [week2/incident_rollback.py](../../week2/incident_rollback.py) | Inject cooldown persistence and pass the remaining execution budget to bounded work. Preserve C1 checks and existing callers. |
| `week2/tests/test_capacity.py` and `week2/tests/test_capacity_mount.py` (new), [week2/tests/test_abuse_guard.py](../../week2/tests/test_abuse_guard.py) | Cover clock boundaries and two processes, then exercise the actual authenticated Gradio mount and cooldowns. Reuse existing identity and storage fixtures. |
| `week4/capacity_load.py` (new), [.github/workflows/week2-4.yml](../../.github/workflows/week2-4.yml) | Produce the local load report. Run fast deterministic capacity checks with the existing CI suite and verify their evidence. Run the ten-minute rehearsal separately. |

## Order of work

1. **Commit the failing regression first.** On the accepted baseline, build the
   pinned Gradio app and assert a finite pending limit and a shared execution
   group for all review callbacks. Record the observed assertion failure before
   changing runtime code. Use the mount inventory to identify submit, retry,
   named chat and recovery bindings, plus lightweight UI callbacks. Verify the
   inventory against the mounted app at startup, including the suggested-option
   selection path that the pinned ChatInterface also registers, so new work-bearing bindings
   cannot silently run unclassified.
2. **Implement the local reservation ledger.** Use a private, temporary SQLite
   database shared by the two same-host test processes. Follow the project's
   [file permissions and transaction patterns](../../week2/memory.py). In a
   short write transaction, expire eligible records, check principal and global
   limits, assign arrival order and reserve exactly once. Never hold the
   transaction during a review. Store opaque IDs, scoped keys, state, ownership
   generation and times. Keep prompts, source text and email addresses out
   of the ledger. Pass an explicit database path to the local test mount so
   restarting the app or starting a second process opens the same file.
   Refused work costs no rate token. A failed handoff before acceptance rolls
   back its provisional reservation. After acceptance, the charge survives failure
   or cancellation. Bound and prune expired accounting records.
3. **Connect admission to the UI and direct paths.** After IAP and session
   validation, resolve the actual mounted function for each supported call.
   Where routing requires parsing the body, retain the mount's 256 KiB limit
   and discard refused input before Gradio can store it.
   Reserve at the first submit/retry step, before Gradio saves the message or
   updates history. Pass the server-owned operation through the event chain.
   Bind Gradio's generated event ID to that operation and check it again at
   worker entry. Supported direct chat and recovery calls enter the same
   scheduler. Reject inconsistent operation identities before invoking a
   callback. A delivery retry reuses its receipt. A deliberate resubmission
   gets a new one, even for identical text. Use a finite Gradio queue and one
   shared execution group. Test that admission accounts for all waiting work.
4. **Dispatch and finish.** Start the oldest eligible reservation under an
   atomic check of its deadline and the running slot. Expire queued work at
   15 seconds. From dispatch, pass the lesser of the remaining 45 seconds and
   each dependency's existing timeout to calls. Check expiry before starting a
   new stage and before exposing its result. A timed-out or cancelled running
   review stops publishing, requests cancellation, and holds capacity until
   its worker exits. Finalize by reservation ID and generation exactly once.
   Preserve existing tool attempt accounting, abuse controls, C1 verdicts and
   private audit behavior for admitted work.
5. **Handle overload and streams.** Return 429 for principal limits and 503
   for shared saturation or an unavailable ledger. Once the ledger is
   available, check principal limits before shared limits so overlapping
   conditions give a consistent answer. Include a bounded integer
   `Retry-After` and send equivalent feedback in the event protocol after headers
   have been sent. Busy feedback preserves chat text, conversation history and
   recovery form fields. It creates no assessment or security strike. Acquire
   an instance-scoped connection permit before opening a stream and release it
   on close, error or cancellation. A reconnect can reattach only to the
   same session's event and consumes no review admission. For review, the
   local fixture proposes an idle-stream timeout of 60 seconds without user
   activity or active work, a 15-second grace period after the last subscriber
   disconnects, and up to four replacement connections per principal per
   rolling minute. Count reconnects separately from reviews. At grace expiry,
   cancel abandoned work unless its review deadline has already ended it. Track
   explicit reattachment to the same event independently of idle heartbeats.
   Exercise each boundary with a fake clock.
6. **Prove safe recovery.** Use a stable key derived from the verified principal
   for local quota and cooldown lookup. Preserve the existing private audit
   identity boundary. Persist expiry on a clock meaningful after restart.
   Use monotonic time for elapsed work. On restart, discard the dead worker's
   queued payloads, resolve their reservations and retain valid rate charges
   and cooldowns. For the same-host fixture, use process-owned OS locks to
   confirm worker death before reclaiming its running slot. An expired timer
   alone cannot establish death. A stale completion must fail its generation
   check. Document any implementation deviation in this plan in the same commit.

## Risks

- **The queue join and the callback are separate events.** Gradio's chat chain
  currently clears the textbox before the review callback. Tie the draft and
  reservation to the same logical submit and confirm the behavior in a browser.
  Include handoff failure, duplicate delivery and simultaneous submissions
  from one session in this test.
- **A timeout can precede actual worker termination.** Exercise a deliberately
  slow synchronous collaborator past the deadline. A second review must wait
  until the first worker stops, and the first result must stay suppressed.
- **Persistence can give false confidence about production.** The local
  SQLite and process-lock fixture tests restart and contention on one host.
  Shared cloud storage, retention, cross-instance ownership, service targets,
  billing and permission changes remain separate owner decisions.

## Proof

Three existing controls passed locally on Python 3.13 before implementation.
They cover owner access at the Gradio mount, session ownership and security
cooldown retries. The scenarios below will verify the C2 behavior.

The first C2 regression commit (`806fc0c`) recorded both baseline failures:
the native queue had no maximum, and the five review bindings occupied three
separate execution groups. Suggested-option selection, retry and textbox
submission share a chat wrapper. The named chat API and recovery each have a
separate wrapper. Inspect the callback registrations when updating Gradio.

The local protected mount accepts a private database path as a test fixture.
Direct chat and recovery requests share its reservation ledger. The restart
test opens the same file in a second process. A separate crash test holds the
running slot in a child process and observes when the operating system releases
the file lock. The browser event chain and load rehearsal have their own
acceptance checks below.

In that fixture a submit, retry or suggestion is one Gradio callback. This
keeps the user's draft and previous answer in place until the admitted callback
returns, and removes the gap between Gradio clearing the draft and scheduling
the review. A browser gesture carries an opaque delivery ID. A retransmission
gets the same event handle. Direct clients may send a 32-character lowercase
hexadecimal `Idempotency-Key` and receive the existing receipt on replay.
All five work-bearing callbacks use the same ledger. The original published
interface remains available outside the local fixture.

The browser smoke test exposed a Gradio behavior visible only after a real
refusal. Marking the textbox and conversation as outputs blanked them on a
failed queue join. In the local mount the review writes to session state,
then publishes visible outputs only on success. The smoke test now checks the
previous answer, the draft and the retry message in Chrome. The browser uses
Gradio's generic `predict` path for lightweight callbacks. Resolve those calls
by their actual function index so identity and status updates still work.

Run `python -m week4.capacity_load --scenario smoke --out smoke.json` or
`python -m week4.capacity_load --scenario rehearsal --out rehearsal.json`
with the Week 2 development environment, Node, Chrome and Playwright available.
Set `CRA2_PLAYWRIGHT_MODULE` to the installed Node module if it is outside
Node's normal search path. [Browser driver](../../week4/capacity_browser.cjs)
and [fixture](../../week4/capacity_load.py) create a temporary loopback app,
isolated browser contexts and synthetic signed identities. The fixture uses
the private local ledger. Record exact-revision measurements for owner review.

The first full rehearsal exposed missing visible results after repeated tab
replacement. The added [lifecycle tests](../../week2/tests/test_capacity_lifecycle.py)
exercise signed burst traffic, cancellation, deadlines and reconnects. A separate
regression proved that an idle heartbeat or queue stream could hold a permit
until its next write after socket disconnect. Watch the incoming disconnect
alongside the SSE producer and release the permit exactly once. Keep HTTP outcome
counts in the local rehearsal so a browser timeout can be traced to a route.

The mount also checks whether a result stream can open before handing a new
browser review to Gradio. A session with an existing data stream can reuse it.
When both connections are occupied elsewhere, the provisional reservation is
released and the user receives a bounded 503 retry. Lightweight page-load
callbacks use the direct path. Gradio substitutes a generic toast for every
503, so the fixture also displays the server's retry hint in an accessible
notice. The Chrome smoke case fills both connections, verifies that the
recovery form retains its draft, closes one tab, and resubmits the same form.

| Scenario | Passing evidence |
|---|---|
| Admission and FIFO | Hold one worker, queue two eligible reviews and refuse the next otherwise eligible submission with 503. Separately hit 2 outstanding and 4 admissions in 60 seconds across tabs and direct calls and verify a 429 response. Check the rolling-window boundary and retry hint. Force a ledger failure (503) and a failed pre-acceptance handoff (no charge or orphan). Refusals leave classifier, retrieval, tools and reviewer call counts at zero. Oldest eligible work starts next. |
| Deadline, cancellation and restart | With a controlled clock, test immediately before and at 15 and 45 seconds. Race cancel, completion and retry. Expire a waiter, then interrupt a worker and restart against the same file. Two independent processes must respect the global bounds. Confirm one terminal outcome, no early slot reuse and no quota or cooldown reset. |
| Browser, identity and streams | Use local synthetic signed identities at the protected mount. Fill the two connection slots, refuse a third with a retry hint, and use cancel/status during saturation. Disconnect and reattach just before grace expiry. Separately let grace or the review deadline expire. Verify idle/reconnect bounds, draft preservation, event ownership, and existing unauthenticated and uninvited responses. Duplicate delivery charges once. An explicit resubmission of identical text counts as a new review. Keep a browser observation for visible behavior alongside HTTP/event assertions. |
| Rehearsal | Schedule 40 logical submissions at 15-second intervals over ten minutes, alternating chat and recovery across two synthetic principals. Measure bursts separately. Record idle tabs and reconnects. Reconcile offered = admitted + refused, and admitted = completed + failed + expired + cancelled after drain. Running, waiting and open-stream counts must all return to zero after clients close. |

Run the accepted mixed workload against two synthetic signed identities on
loopback. Each identity submits ten checkout timeout changes and ten inventory
schema rollbacks in fresh tabs. Verify the visible 90% decrease and operational
checks in chat, and the incomplete recovery evidence, incident CX-109, direct
callers and rollback source in the recovery report. Match each visible result
to its completed event, signed identity and browser session. For each chat event
also match the persisted evidence-only trace with completed retrieval and tool
stages. Record cache hits and misses for this repeated workload. The smoke test
interrupts a read of the result stream and exercises overload feedback in both
forms. The local mount permits the authenticated Gradio process-ID read used for
reconnect, and bounds retries of the existing result stream within the grace period.

The follow-up browser regression holds the first answer in transit and types a
new draft in that tab. The earlier completion cleared the textbox unconditionally
at baseline `ef2e3af`. A successful publish now returns its validated delivery
ID. The browser clears only a still-unedited draft from that submission. The
smoke check covers delayed publication, both overload refusals, recovery retry,
and normal clearing after an untouched successful submission. The original
pre-commit refusal mismatch lacked an operation label, so its attribution
remains open.

Archive the revision, Python/Gradio versions, actual limits, workload mix,
per-outcome counts, observed maxima, and p50/p95 queue and submission-to-visible
latencies with sample sizes. Report expected overload separately from unexpected
errors. Mark missing samples, lost events or a failed drain as inconclusive.
Preserve the Week 2–4 C1, evaluator and fault checks. Local results establish
the fixture's behavior. Live IAP timing, platform timeouts, billed time and a
1,000-user capacity claim require separate measurements and owner-approved targets.
