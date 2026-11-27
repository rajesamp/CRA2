# Intent · Google-authenticated invitations and user access

Originator: CRA2 owner. Accepted by the owner on 2026-11-26, including the clarifications below. Stage 1 of the AI-native SDLC.

## Problem

The owner wants one designated Google account to own CRA2 and a separate user role for everyone else admitted to the workspace. They want a **Send invite** action, a fast “System 1” classifier for valid or spam requests, suppression of repeated invitations, and a Google Sheet to track what happened.

The public start screen currently redirects to an owner-only IAP workspace. An uninvited visitor cannot use a request button inside that workspace. CRA2 already verifies signed Google identities and supports a configured owner and up to 1,000 allowed email addresses. That configuration limit is not a measured capacity. See the [public entrypoint](../../week2/landing.py) and [identity verifier](../../week2/iap.py).

## Proposed outcome

| Actor | Experience when the feature opens |
|---|---|
| Visitor | From the public start screen, type an email address and verify it by signing in with Google before submitting interest. Receive a generic acknowledgement that does not disclose who is already a member. |
| Owner | Preview eligible requests after System 1 screening. Approve or deny them. Only the owner can use **Send invite**, for an approved requester or a recipient chosen directly by the owner. Revoke outstanding invitations or existing user access. |
| Recipient | Open an expiring, single-use invitation and authenticate as its intended recipient. An eligible recipient enters as a user and sees their own review data. |

There is exactly one owner. Every other user must sign in with Google and redeem an invitation before gaining workspace access. A user's own request, the owner's decision, email delivery, redemption and an access grant are separate, auditable events. Ban actors who repeatedly commit abuse. Suppress ordinary duplicate submissions without penalizing the requester or the typed recipient. The production hold stays in force until the owner explicitly opens invitations.

## Affected users and systems

- The public start screen needs an authenticated request path reachable before membership. The IAP-protected review workspace needs server-side authorization for owner and user actions. The design must explain how IAP admission and application membership agree on grant and revocation.
- The request classifier returns **valid**, **spam**, or **needs review** with a reason and policy version before any request enters the owner's approval queue. Only valid requests appear there. Suppress spam and hold uncertain results for resolution. Classification alone grants no access and sends no email.
- An owner-restricted Google Sheet shows request ID, timestamp, masked recipient, decision, reason, invitation status and suppressed-repeat count. Delivery uses the address approved for that invitation. Redemption verifies control of that address. The sheet is a reporting copy. Editing a cell cannot send mail, change membership or assign ownership.

## Constraints and acceptance evidence

| Risk | What the design and Python 3.13 checks must demonstrate |
|---|---|
| Owner impersonation or lockout | Bind the confirmed owner to a verified Google identity. Test an ordinary user's direct call to an owner action. Rehearse an owner handover and recovery before changing the production owner. |
| Repeats, harassment and races | Double clicks, concurrent requests on different instances, retries after a restart and different senders targeting one recipient produce one pending invitation. Suppress further sends during the agreed cooldown. Record repeats without labeling an ordinary retry as spam. Reconcile an ambiguous email-provider timeout before retrying. |
| Forwarded links, replay and privacy | Only the intended authenticated recipient can redeem an unexpired, unrevoked invitation once. Test wrong-account, expired and reused links, cross-user data access and cross-site send attempts. Keep addresses and invitation secrets out of public responses and logs. |
| Classifier errors and abuse | Start with synthetic valid, spam, duplicate and ambiguous cases. Report false blocks of legitimate requests, spam admitted to review, review volume and decision latency. Use bounded signals such as identity verification and sender/recipient rate history. A shared network or an unfamiliar address alone is insufficient to discard a request. |
| Scale, cost and Sheets failures | Exercise a burst against the same recipient and a burst across distinct recipients on multiple instances. Measure queue age, p95 latency, email volume, suppressed duplicates and reporting lag. Bound sender and recipient rates and total delivery volume. Simulate a Sheets quota response and an outage. Batched retries must reconcile by event ID without sending another invitation. Write untrusted cell values as literal text. [Sheets limits](https://developers.google.com/workspace/sheets/api/limits) · [Value input modes](https://developers.google.com/workspace/sheets/api/reference/rest/v4/ValueInputOption) |

Use a mail sink, synthetic identities and a test reporting destination during development. Keep independent labeling on hold. Production email delivery, owner transfer, IAM updates and sharing a live Sheet require a later rollout decision.

## Open questions

1. The owner will confirm the full Google account privately before any transfer. A local part, display name or Git author address cannot establish ownership.
2. What invitation lifetime, resend cooldown, abuse threshold, ban duration, appeal process and revocation delay fit the owner's invitation plans?
3. What are the expected launch batch and peak request rate, mail budget, acceptable false-block rate and maximum manual review volume? Agree on targets before grading the classifier or claiming capacity.
4. What reporting fields and retention periods does the owner need? The default reporting audience is the owner alone.
