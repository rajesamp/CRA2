# Cloud Run delivery sequence

Updated 2026-11-16. Target: a browser-accessible demo for **an allowlist of invited
Google accounts**. The user refined the earlier public/anonymous assumption.
No service has been deployed by this work. **Owner acceptance comes first.** The
two prospective invitees are held in ignored local configuration. No invitation,
message or access grant to them is permitted before the owner tests the app and
explicitly approves inviting users. First deployment is for owner acceptance only.

The owner has now supplied a **USD 10/month planning budget** (USD assumed).
See the [cost assumptions and 1,000-user calculation](cloud-run-budget.md).
The frozen design assessments below predate that amount; they are historical
and do not establish that a deployed architecture fits this budget.

## UI framework flexibility

The owner permits replacing Gradio with Streamlit if it makes delivery easier.
The earlier plan covered only Gradio, so that comparison was incomplete. The
expanded [immutable manifest](../intent/guardrails-ci-cloud-run/ui-framework.pinned.json)
and [fresh judge result](../intent/guardrails-ci-cloud-run/ui-framework.judge.json)
assess both options. Continuing Gradio is **suitable**; **winner not established**.
No UI code or dependency has been changed by this assessment.

The existing Gradio build has local test and container evidence. Streamlit has
[documented Cloud Run hosting](https://docs.cloud.google.com/run/docs/quickstarts/build-and-deploy/deploy-python-streamlit-service),
but CRA2 migration effort and behavior parity have not been measured. The encoder
mirror blocker is in model provisioning. Changing only the UI would leave that
blocker, verified identity, persistent user state and owner acceptance unresolved.

The smallest separating test is one isolated Streamlit chat slice using the same
guarded workflow, cooldown and trace helpers: normal/refused requests, two
sessions, clear/undo and trace display. Compare implementation time and required
changes with the existing Gradio baseline. If authenticated transport is the
actual blocker, run matching owner-controlled IAP allow/deny and reconnect tests
for both frameworks before claiming it is resolved. Switch when that evidence
shows the benefit without dropping required behavior.

⟦ verdict · sha256=d5ad1651bf490ea3788effa67aa28d646332a1565ce08e08116e4288bbfc873c · level=suitable · delta=option_added ⟧

## Access decision for the recorded Gradio baseline

Retaining Gradio is no longer a user requirement. The frozen access manifest
below describes the existing implementation; a Streamlit migration would require
a revised access manifest and verification of its authenticated transport.

Direct Cloud Run IAP is **suitable**, conditional on deployed verification;
**winner not established**. The fresh judge evaluated direct IAP, load-balancer
IAP and application Google sign-in from the immutable
[manifest](../intent/guardrails-ci-cloud-run/iap-access-v2.pinned.json).
The [judge result](../intent/guardrails-ci-cloud-run/iap-access-v2.judge.json) and
[validation harness](../intent/guardrails-ci-cloud-run/validate_verdict.py) retain
the decision and computed hash. There is no comparative authentication evidence.

The smallest separating test is the same allowed/denied-account, signed-out,
forged-header, direct-URL and Gradio-streaming probe through direct IAP and the
load-balancer alternative. Use owner-controlled test accounts during acceptance;
prospective invitees remain outside the access policy. This is a design assessment,
not a deployed-security pass.

⟦ verdict · sha256=4e20e9428947d367adb01e42f09793939eccdea4d6fc83a1fd33eafd5b21d827 · level=suitable · delta=requirement ⟧

Google documents direct IAP coverage of Cloud Run ingress, principal allowlists,
and external OAuth setup for Gmail/out-of-organization invitees. The intended
binding is service-scoped `roles/iap.httpsResourceAccessor`; the IAP service agent
needs Cloud Run invocation permission. Deployment privileges belong to the
deployer, not the runtime service account.
[Direct IAP setup](https://docs.cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run)

## Ordered work and exit evidence

| Order | Work | Exit evidence | State |
|---|---|---|---|
| 0 | Fix output rail and visible-answer scoring; add Week 2–4 CI | Local tests; 18+4 evals; 7 scorer controls; 9 faults; first GitHub run | Code/tests complete; approved encoder mirror published/configured; GitHub run pending |
| 1 | Container/startup contract | Explicit `0.0.0.0:$PORT`, local loopback default, invalid-port rejection; nonroot Linux/amd64 image; 6/6 real local RAG/MCP/NeMo intents; HTTP 200 and blocked file read | Automated local verification passed; owner acceptance pending |
| 2 | Supply-chain release | Distroless nonroot digest; Syft SBOM; Grype scan policy; signature verification; cosign signature and SLSA provenance for immutable output digest | SBOM/scan gate implemented; actual scan blocks release; output signing/provenance pending |
| 3 | IAP and trusted identity | Owner-controlled allowlisted test account succeeds; unlisted/signed-out account denied; no alternate ingress bypass; signed assertions verified; chat queue/stream endpoints covered | Signed-assertion middleware and owner-only Gradio mount implemented/tested; real Google/IAP deployment proof pending |
| 4 | Identity-scoped application state | No cross-user overwrite or trace disclosure; explicit team-write authority; restart and two-instance persistence; bounded retention without the current 2,000-row terminal stop | Pending |
| 5 | Runtime security and capacity | Dedicated least-privilege SA; controlled secrets; default-deny egress with explicit destinations; durable privileged-action audit; request/concurrency/instance budgets | Pending |
| 6 | Deploy and rehearse | Immutable signed revision, IAP negative tests, real browser walkthrough, fault/rollback drill, measured latency/cost/load report | Pending |
| 7 | Invite users only after owner approval | Recorded owner acceptance and explicit approval; then apply the reviewed invitee bindings and separately authorized communications | On hold |

IAP login does not by itself establish team-write permission. The cloud entrypoint
now derives a stable opaque abuse identity from the verified issuer/subject, and
Gradio receives it through a server-owned authentication dependency. Signature,
issuer, exact audience, expiry and token lifetime are verified; plain email and
forwarded headers do not establish identity. The local entrypoint retains its
loopback behavior and refuses to start when `K_SERVICE` is present.
[Signed IAP identity](https://docs.cloud.google.com/iap/docs/signed-headers-howto)

`python -m week2.cloud_app` is the separate cloud entrypoint. It requires a single
`CRA2_OWNER_EMAIL` and the exact service `CRA2_IAP_AUDIENCE`. It intentionally does
not consume prospective invitees. Only content-free `GET /healthz` bypasses
authentication; HTTP and WebSocket application routes are covered. Ephemeral
state remains a deployment blocker even for this owner-only milestone.

Cloud Run's writable filesystem is ephemeral. The container's `/tmp` SQLite
paths support build/smoke verification only; neither single-instance settings nor
session affinity prove durable memory or audit retention. The model and synthetic
index are provisioned into the image, so startup requires no model download.
[Runtime contract](https://docs.cloud.google.com/run/docs/container-contract)

## Step 1 commands

Use the user's Podman runtime; the build context excludes local environments,
databases, credentials, learning notes and Git history. Its only cache input is
the exact checksum-pinned public encoder archive. The original Qdrant archive URL
now denies anonymous reads with HTTP 403, so clean CI needs a reviewed reachable
copy configured as `CRA2_MODEL_ARCHIVE_URL`. The owner approved publication and
the [verified build asset](https://github.com/rajesamp/CRA2/releases/tag/build-deps-bge-small-en-v1.5-3858004b3822)
is now published. The repository variable is configured for both CI workflows.
An anonymous fresh-cache download passed the archive and all seven installed-file
hash checks and built the 68-chunk index. See the [publication evidence](evidence/encoder-mirror-2026-11-16/README.md).

```sh
# Set CRA2_BUILD_CONNECTION to the verified Podman connection on your machine.
podman --connection "$CRA2_BUILD_CONNECTION" build --platform linux/amd64 -f Containerfile -t localhost/cra2:cloud-run-check .
week2/.venv/bin/python scripts/check_container.py localhost/cra2:cloud-run-check \
  --connection "$CRA2_BUILD_CONNECTION" --out /tmp/cra2-container-evidence.json
podman --connection "$CRA2_BUILD_CONNECTION" run --rm -p 127.0.0.1:8080:8080 localhost/cra2:cloud-run-check
```

The final command uses the local entrypoint, without cloud login. It is not a
public deployment command. Preserve the existing legacy QEMU
VM while restoring a compatible Podman engine or using an independent build VM.
The recorded CLI is Podman 5.0.2 and reports QEMU as unsupported.
An independent build VM was used successfully and stopped after verification;
the original default connection was restored. The [container report](evidence/guardrail-ci-2026-11-16/container.json)
records the exact tested image and source hashes. Its HTTP check runs inside the
container with networking disabled; an owner browser walkthrough remains pending.

## Owner acceptance and invitation hold

Automated checks do not count as owner acceptance. Record the owner's result and
revision for each item below after deployment prerequisites are complete:

| Owner walkthrough | Required result | Owner result |
|---|---|---|
| Six demo intents, including memory and approval refusal | Correct displayed answer and supporting evidence | Pending |
| Unsafe authorization and dependency failures | Protected response; no operational approval | Pending |
| Google sign-in and alternate URLs | Owner admitted; signed-out/unlisted account denied; queue and streaming work | Pending |
| Identity, memory and audit | No unintended cross-user access; approved persistence survives restart | Pending |
| Load, limits and recovery | Recorded latency/cost assumptions, enforced limits and successful rollback | Pending |

Only after these owner checks pass may invitation planning resume. Applying
prospective-user access bindings and sending invitations both require the owner's
later explicit approval. The ignored local hold flags are planning records, not
an implemented IAM enforcement control. This change makes no IAM grants.

## Configuration and 1,000-user evidence

Configured authentication, project reads and billing-enabled status have been
verified. Cloud Billing API was enabled on the target project for this read;
an explicit target quota project was required. This does not prove all deployment
permissions. No service, image publication or IAM grant was created. Keep actual
identifiers, invitee emails and OAuth secrets in ignored local configuration or
managed secrets. Review the concrete target/IAM change set before applying it.

Before a 1,000-user claim, distinguish registered users, daily active users and
simultaneous requests. Record queries/user/day, arrival bursts, provider-mode mix,
input/output tokens, cache hit rates, p50/p95 latency and instance concurrency.
Calculate requests/day = daily active users × queries/user/day; active-request
concurrency ≈ peak requests/second × measured mean duration. Price measured
instance time, model usage, durable storage and egress in the selected region.
An instance limit bounds capacity, not total provider spend. Alerts-only budgets
are notifications. Cloud Run spend caps are now documented but have delayed
enforcement and a service/project scope; see the budget note. Per-user and
aggregate request/token limits and measured stream duration remain required.

Before applying infrastructure, prepare the target-specific IAM/resource diff and
cost limits. An invite-only service must not gain an unauthenticated invoker
binding. Treat any irreversible audit-retention lock as its own explicit action.
