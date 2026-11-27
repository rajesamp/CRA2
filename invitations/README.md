# CRA2 invitation pilot

Run this separate service to rehearse the invitation workflow with synthetic identities. It binds to loopback, starts paused, and stores its state in a private directory. It has its own Python 3.13 dependency lock and CI job. CRA2's application, IAP owner check, public sign-in page, risk classifier and container do not import or launch this module.

## Try the owner and recipient flows

From the repository root, create the isolated environment and start the server.

```sh
uv sync --locked --project invitations --python 3.13
invitations/.venv/bin/python -m invitations --state ~/.local/state/cra2-invitation-pilot serve
```

Open [the local pilot](http://127.0.0.1:8098/) in two separate browser profiles. The synthetic accounts are `owner@example.test`, `reviewer@example.test` and `second@example.test`. Use the local shell to retrieve the sign-in key for each profile. Keep the state directory private. Its key is equivalent to control of the local simulation.

```sh
invitations/.venv/bin/python -m invitations --state ~/.local/state/cra2-invitation-pilot signin-key owner@example.test
invitations/.venv/bin/python -m invitations --state ~/.local/state/cra2-invitation-pilot signin-key reviewer@example.test
```

1. Sign in as the fixture owner and select **Enable local invitations**.
2. In the recipient profile, enter the reviewer's email, sign in and choose **Confirm interest**. Refresh the owner's review queue. **Approve** makes **Send approved invite** available. **Deny** closes the request.
3. Send the invitation and read the synthetic mailbox. The background worker normally delivers within a second.

   ```sh
   invitations/.venv/bin/python -m invitations --state ~/.local/state/cra2-invitation-pilot mailbox reviewer@example.test
   ```

4. In the reviewer's profile, enter the code and select **Redeem invitation**. Return to the pilot and open **Pilot workspace** when local provisioning completes. The code expires exactly 600 seconds after the original mail receipt. Starting sign-in or refreshing the page consumes none of the code's state and never extends that deadline.
5. Revoke the reviewer from the owner page. Refreshing the reviewer's workspace now denies access. The owner can inspect **Private reporting copy**. Stable event IDs make this simulated Sheet rebuildable after an outage.

The admission service also accepts owner-direct invitations. An existing pending or denied request goes through the decision queue first. Submitting interest sends no email. Pausing the pilot stops intake, delivery and new grants at the server.

## System 1

The classifier in `policy.py` references the typed decision and abstention design in [Laya, revision 073afac](https://github.com/NandhaKishorM/laya/tree/073afac82616383088943b95ab4412b9324a9449). This implementation evaluates verified account and request-history facts locally. It loads no model weights and sends no user data to Laya. Each decision carries an outcome, reason and policy version. Only `valid` creates a review item. Uncertain identity is held, ordinary repeats are coalesced, and a first address mismatch prompts correction.

Three distinct third-party targets after a warning qualify one ten-minute abuse window. Three such non-overlapping windows in seven days ban the verified actor for seven days. A repeated click, expired code or shared network earns zero strikes. The owner can review one appeal per ban and lift an erroneous ban.

## Verification and boundaries

Run the policy, fault, authorization, concurrency and 1,000-account tests with `invitations/.venv/bin/python -m pytest -q invitations/tests`. Set `INVITATION_BROWSER=1` and `CRA2_PLAYWRIGHT_MODULE` to the installed Playwright module to include the real Chrome test. The invitation CI job runs that probe. The JUnit output includes the synthetic classifier counts and local workload measurements.

The pilot simulates Google's identity provider, delivery, access provisioning and an owner-restricted Google Sheet. The workspace page demonstrates only the synthetic user's role. The state directory can be reopened after a restart. A local SQLite workload does not establish Cloud Run capacity. Real owner identity, external integrations, independent labeling and production rollout are separate decisions.


## Local staging identity adapter

The separate ASGI factory `invitations.staging.app:from_env` implements the identity check for the planned owner-only staging service. The loopback invitation CLI above continues to use its own fixture accounts. The staging factory exposes a sign-in page, an OAuth callback, logout, a content-free health check and an owner verification result. It starts without invitation workers.

Run the local regression without Google credentials from the repository root:

```sh
invitations/.venv/bin/python -m pytest -q invitations/tests/test_staging_identity.py
```

To include the cross-site HTTPS Chrome test, set `INVITATION_BROWSER=1` and `CRA2_PLAYWRIGHT_MODULE` as for the existing browser check. The test maps the sign-in host to a loopback TLS provider, verifies independent IAP and OIDC signatures, and follows the real browser cookie and redirect path.

The factory reads these explicit settings. Keep OAuth secrets, email addresses and identity pins out of version control. Keep HTTP access logging disabled for the callback, which carries a short-lived authorization code.

| Setting (prefix every name with `INVITATION_STAGE_`) | Value |
|---|---|
| `ORIGIN`, `IAP_AUDIENCE` | Exact HTTPS origin without a trailing slash and exact direct-IAP audience for the dedicated service ending in `-staging`. Supply actual values through private operator configuration. The registered redirect is `ORIGIN/auth/callback`. |
| `CLIENT_ID`, `CLIENT_SECRET`, `OWNER_EMAIL` | Application web OAuth client credentials and the privately confirmed full Google account. |
| `STATE_DIR` | Dedicated private local directory (mode 0700) for pending attempts and sessions. Use a fresh directory for a new enrollment exercise. |
| `MODE`, `OWNER_PIN` | Start in `verify-only` with the pin unset. After the operator confirms the account and matching proofs, use `enrolled` with the explicitly approved pin. |

The sign-in transaction expires after five minutes. A successful callback rotates the cookie and establishes a fifteen-minute session bound to the same IAP identity and configuration. During private enrollment, run `invitations/.venv/bin/python -m invitations.staging candidate-pin` locally with the same verify-only settings. It reads the unique current verified candidate, prints its pseudonymous pin to the private terminal, and never enrolls it. Enrolled mode requires a fresh Google sign-in. Keep the terminal result out of shared evidence. Live Google sign-in, Cloud Run, IAM changes and real invitations are outside this local slice. [Approved staging plan](../intent/invited-user-access/cloud-run-staging-plan.md)
