# Implementation plan · Invitations and user access

**Local implementation authorized · 2026-11-26.** Based on [approved local spec](spec.md) at `bc54ef1`, from [intent](intent.md) at `528dfa3`. The deliverable is a local end-to-end pilot on Python 3.13. Production stays owner-only. Real invitations, external account grants and independent labeling remain on hold.

## Files and order of work

The owner requested a separate module with a Laya reference. Build `invitations/` at the repository root. The CRA2 wheel and container already allowlist their inputs. Keep all existing CRA2 entry points, authentication, risk routing, dependencies, pipelines and deployment configuration intact. Use a separate path-scoped invitation CI job.

1. Implement a typed, versioned decision contract in `invitations/policy.py`. Use Laya's typed answer and abstention pattern from [the pinned Laya source](https://github.com/NandhaKishorM/laya/tree/073afac82616383088943b95ab4412b9324a9449). Feed the classifier verified facts only. No classifier action can send an email or authorize access. Use synthetic controls for each disposition.
2. Build the transactional store, moderation, owner decisions and single-use invitation lifecycle in `invitations/`. Exercise restarts, replay, per-account clocks, rate controls and concurrency with independent database connections.
3. Implement separate local mail, membership and Sheet fixtures. Prove original receipt reconciliation, pending/revoked membership behavior, report repair, bounded retention and the global hold without provider credentials.
4. Expose the pilot through its own loopback browser entry point. Use signed synthetic identity, separate owner/recipient sessions and CSRF-protected actions. Show member access only to an isolated demonstration page. Run the browser and capacity checks alongside the module's own tests.
5. Run CRA2's existing offline suites on Python 3.13 to check isolation. Document the local entry point and evidence. Keep production integrations deferred.

## The ten-minute redemption contract

Start the clock at the mail sink's first confirmed acceptance of the email. Persist that original UTC instant as `sent_at` and set `expires_at = sent_at + 600 seconds` for that invitation. The email explains the window. Show the exact deadline only to the matching signed-in recipient once the receipt is known. Never take the time from a browser or restart the clock on a callback, retry or page view.

Read authoritative time **after acquiring the write lock** and use it in the conditional consume operation. At `now >= expires_at`, an unused invitation is expired, even if cleanup has yet to mark the stored row. A repeat of an already successful redemption by its recipient may return its original status, with no new grant. An expired code earns no strike and triggers no replacement email. The separate 24-hour replacement cooldown still applies to an explicit owner replacement.

| Fake-clock exercise | Expected result |
|---|---|
| Mail queued at 11:58 UTC and accepted at 12:00 | Deadline is 12:10 UTC. Time in the dispatch queue consumes none of the recipient's ten minutes. |
| Three fresh fixtures submit at 12:09:59.999, 12:10:00.000 and 12:10:00.001 | One timely redemption. Both remaining codes are expired. Neither creates a membership or provisioning event. |
| Another recipient's email is accepted at 12:04 | At 12:10 the first unused code is expired and the second is valid until 12:14. A code presented by the wrong Google account cannot consume it. |
| The recipient starts sign-in before expiry, submits after expiry, or waits on the database lock across the boundary | Reject the late consume. Opening the email or starting sign-in does not reserve access. |
| Sink accepts at 12:00 but the worker recovers the receipt at 12:11 after a restart | Keep the 12:10 deadline, mark the unused invitation expired, and suppress redispatch. With no trustworthy original receipt, leave delivery unresolved. |
| Two instances race just before expiry; provisioning finishes after expiry | Only one transaction consumes the code. Its membership can finish provisioning. A later replay creates nothing. |

## Other acceptance checks

- **Abuse and appeal.** Exercise two actors on a shared network. For the offending actor, generate the initial self-only warning, then three distinct mismatched targets in each of three non-overlapping ten-minute windows within seven days. Verify at most one strike per window, a seven-day ban at the third qualifying window, and zero strikes for the typed recipients. Test just below each threshold, repeats of the same target, duplicate submissions, the seven-day lookback, ban expiry and one authenticated appeal per ban. An ordinary invitation expiring must not advance any moderation clock.
- **Races and holds.** Race 100 equivalent interest submissions and 20 owner sends across two instances, then restart one instance. Exercise approve versus deny, revoke versus dispatch, revoke versus redeem and a stale grant worker. Reactivate the hold with work already queued. Record zero new sends and zero new grants after the hold takes effect. An email already accepted by the sink remains auditable; a revoked code is unusable.
- **Classifier and capacity.** Use a fixed synthetic dataset with known dispositions, a policy version and explicit sample counts. Report legitimate requests suppressed, spam admitted to preview, inconclusive holds and unnecessary strikes separately. Run 1,000 distinct synthetic accounts over ten minutes plus a separate same-recipient burst. Report p95 latency, throughput, queue age, suppressed duplicates, send count, reporting lag and error counts. A local SQLite run establishes local behavior only.
- **Security and privacy.** Exercise direct non-owner API calls and cross-user sessions, a forwarded or expired code, attempted replay, and a Google identity that cannot be bound to IAP. Verify no secret appears in URL, logs, public HTML, Sheet cells or CI artifacts. Public signup remains unavailable under the production configuration. Record browser results for request received, owner approval/denial, invitation sent, expired code, timely redemption and revoked access.

## Python 3.13 verification

Run from the feature checkout with each module’s own locked environment. For the full suite, follow the existing CI encoder provisioning step and build the synthetic index first. Use offline settings from the workflow, loopback fixtures and a temporary writable test directory. All commands below describe post-implementation checks.

```sh
uv sync --locked --project week2 --python 3.13
week2/.venv/bin/python -c 'import sys; assert sys.version_info[:2] == (3, 13)'
uv sync --locked --project invitations --python 3.13
# The invitation CI workflow sets CRA2_PLAYWRIGHT_MODULE to its installed Playwright package.
INVITATION_BROWSER=1 invitations/.venv/bin/python -m pytest -q invitations/tests --junitxml=/tmp/cra2-invitation-pilot.xml
week2/.venv/bin/python -m pytest -q -m "not live" week2/tests week3/tests week4/tests --junitxml=/tmp/cra2-invitation-tests.xml
```

Use a fake clock for expiry and ban checks so CI never waits ten minutes or seven days. Require named boundary, authorization, hold, duplicate and recovery cases to execute without skips. Preserve JUnit results, a classifier confusion table and a bounded browser/load summary tied to the Git revision. Preserve existing evaluation controls. Independent labeling remains on hold.

**Planning baseline.** Before implementation, 52 existing landing and IAP tests passed on Python 3.13.15. These cover the current access boundary. The invitation tests and browser/load evidence above are deliverables of the build.

## Risks and release boundary

The principal risks are extending a code during mail reconciliation, granting a membership after expiry or revocation, conflating an email alias with a stable identity, and treating Sheets as an authorization source. Use the transactional checks and failure fixtures above as release criteria. Roll back the pilot by closing intake, send and grant gates, invalidating unredeemed codes, and retaining audit evidence and existing owner access.

Plan approval would authorize local implementation and synthetic checks. A production datastore and mail provider, verifiable original acceptance timestamps, real OIDC-to-IAP identity binding, permissions, funded capacity limits, retention, owner account proof and rollout approval belong to a later release decision.
