# Cloud Run delivery sequence

Updated 2026-11-19. Target: a browser-accessible demo for **an allowlist of invited
Google accounts**. The user refined the earlier public/anonymous assumption.
A healthy owner-only revision is deployed. Owner Google login and local chat
have been verified in a browser. **Owner product acceptance comes first.** The
two prospective invitees are held in ignored local configuration. No invitation,
message or access grant to them is permitted before the owner tests the app and
explicitly approves inviting users. First deployment is for owner acceptance only.

The owner has now supplied a **USD 10/month planning budget** (USD assumed).
See the [cost assumptions and 1,000-user calculation](cloud-run-budget.md).
The frozen design assessments below predate that amount; they are historical
and do not establish that a deployed architecture fits this budget.

## Live owner deployment: owner product acceptance pending

The [bounded rollout evidence](../intent/cloud-durable-storage/live-owner-rollout.json)
records deployment of source commit `903583849055174f6ffa0243fc503a29fd1a92d7`.
The private registry digest matches the scanned image configuration. Cosign
verified its KMS-backed signature and signed SLSA v1 statement. Provenance is
operator-generated for the local Podman build; no SLSA build level or public
transparency-log entry is claimed. The scan examined 159 packages and four
matches: three Medium, one Low, zero blocking; its positive detection control
reported 27 blocking matches.

Cloud Run reports Ready with direct IAP enabled, IAM invocation checks, a
dedicated runtime identity, one maximum instance, zero minimum instances,
1 vCPU, 2 GiB, request-based CPU and concurrency four. The service IAM inventory
has one Run invoker (the IAP service agent) and one human IAP accessor (owner).
The service uses dedicated all-traffic VPC egress with an allow rule for the
Storage API and IAP public keys and a deny rule for other IPv4 destinations.

Two separate Cloud Run job executions used that exact image, runtime identity,
network and application storage code. The first wrote a synthetic preference
and audit attempt; the second recalled it from a fresh instance. Both verified
the permanently locked retention policy, reached the IAP key endpoint and
failed to reach an unlisted HTTPS destination. This proves storage persistence
across fresh runtime executions, not browser-session restart acceptance.

The owner approved a project-local ingress override on 2026-11-18. Effective
values now permit `all` and `internal-and-cloud-load-balancing`; only the demo
service was updated to direct ingress. The parent organization policy is
unchanged. The current account could manage organization IAM but lacked policy
creation permission. Google marks policy-write permissions unsupported in custom
roles. After separate explicit approval, an Organization Policy Administrator
binding with a one-hour expiry was added, the reviewed project override applied,
and the exact temporary binding removed immediately. Final checks found all
original organization IAM bindings preserved and policy creation permission
revoked. No other credential identity was used.
[Permission support](https://docs.cloud.google.com/iam/docs/custom-roles-permissions-support)

The owner separately approved Google's API Services User Data Policy and OAuth
setup. External/testing branding and the IAP client use basic identity/email
only. The client is applied at project `iap_web` scope. Owner Gmail login now
reaches the app. Run IAM and IAP remain enabled, with the IAP service agent as
sole declared invoker and the owner as sole declared human service-level IAP
accessor. No prospective-user grants or invitations were applied.

The [browser evidence](../intent/cloud-durable-storage/live-owner-browser.json)
records four synthetic requests: service help, clarification, a retry change
review and a deployment-approval request. The review exercised retrieval, two
real tool invocations and the memory-policy read; both tools succeeded. The
approval request was blocked at admission. Its metadata-only audit event was
read back by the operator with 30-day retention. Five signed-out or forged-header
requests across both service URL aliases and `/config` redirected to the correct
custom OAuth client. Gradio queue/stream responses completed.

Three workflow latency samples measured p50 795.9 ms and p95 3754.8 ms, excluding
admission screening, IAP, routing and browser rendering. Four requests made zero
external model attempts. Groq credentials and LangSmith uploads remain
unconfigured. Owner product acceptance and a separate non-owner Google-account
browser test remain pending. The image is the tested review baseline; unrelated
uncommitted UI work is not included.

The earlier ingress comparison was incomplete because the inherited restriction
was then unknown. The frozen route assessment below predates the owner's route
authorization and completed browser verification. It does not promote the
selected route to an architectural preference.

The [historical pinned manifest](../intent/guardrails-ci-cloud-run/ingress-route-v2.pinned.json)
and [fresh judge result](../intent/guardrails-ci-cloud-run/ingress-route-v2.judge.json)
rate the project-exception candidate as **possible**, not an authorization or
preference; **winner not established**. The smallest separating test is the same
owner/denied-user, forged-header, endpoint and streaming probe for each approved
route, with observed cost and policy scope.

⟦ verdict · sha256=8e054e7ccb605a6b4df632256f152611c92209b08c98870944b27ff002679f2b · level=possible · delta=evidence ⟧

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
mirror blocker was in model provisioning and has since been resolved by the
approved build-asset publication. Deployed identity verification, persistent user
state and owner acceptance remain separate requirements with either UI.

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
| 0 | Fix output rail and visible-answer scoring; add Week 2–4 CI | GitHub Python 3.10 and 3.13: each 391 tests, 18+4 evals, 7 scorer controls and 9 faults | Passed on both versions using the approved encoder mirror |
| 1 | Container/startup contract | Explicit `0.0.0.0:$PORT`, local loopback default, invalid-port rejection; nonroot Linux/amd64 image; 6/6 real local RAG/MCP/NeMo intents; HTTP 200 and blocked file read | Automated local verification passed; owner acceptance pending |
| 2 | Supply-chain release | Hardened nonroot digest, Syft SBOM, Grype scan and detection control, input signatures, Cosign signature and SLSA provenance for the output digest | Passed. Exact deployed digest has a verified KMS-backed Cosign signature and local-builder SLSA v1 statement. |
| 3 | IAP and trusted identity | Owner-controlled allowlisted test account succeeds; unlisted/signed-out account denied; no alternate ingress bypass; signed assertions verified; chat queue/stream endpoints covered | Owner Google login and Gradio queue/stream verified. Five signed-out/forged-header checks passed across both URL aliases and config. Separate non-owner Google-account browser test pending |
| 4 | Identity-scoped application state | No cross-user overwrite or trace disclosure; explicit team-write authority; restart and two-instance persistence; metadata retention | Live least-privilege storage and permanent 30-day audit lock verified. Preference survived two fresh Cloud Run executions; owner browser acceptance and aged lifecycle deletion remain pending. |
| 5 | Runtime security and capacity | Dedicated least-privilege SA; controlled secrets; default-deny egress with explicit destinations; durable privileged-action audit; request/concurrency/instance budgets | Dedicated identity/network deployed. Allowed and denied HTTPS egress verified. Instance/concurrency limits applied; browser load and cost measurements pending. |
| 6 | Deploy and rehearse | Immutable signed revision, IAP negative tests, real browser walkthrough, fault/rollback drill, measured latency/cost/load report | Healthy signed revision, approved project ingress and external OAuth deployed. Owner local-review smoke and admission block passed; owner product walkthrough, model-backed mode, cost/load measurement and fault drill remain. |
| 7 | Invite users only after owner approval | Recorded owner acceptance and explicit approval; then apply the reviewed invitee bindings and separately authorized communications | On hold |

## First release for owner testing

The deliverable is a verified `run.app` URL for the owner's Google account in
the configured project and region. Use [draft PR #28](https://github.com/rajesamp/CRA2/pull/28)
as the review baseline. Its [Week 2–4 tests and evaluations](https://github.com/rajesamp/CRA2/actions/runs/43965011400)
passed, and its [original container scan](https://github.com/rajesamp/CRA2/actions/runs/43965011390)
blocked the Debian image. The first milestone ends when the owner can sign in and complete
the walkthrough below. Share the verified URL privately with the owner.

1. **Triage the 40 advisory IDs.** Map the 104 matches across 20 Debian binaries
   to source packages. Record the installed version, vendor applicability,
   backported fix version where available, and source for each determination.
   The current Linux amd64 Distroless builder and runtime tags both resolve to
   the existing pins. Rebuilding with only those two tag resolutions supplies
   no updated base. Use the [Debian Security Tracker](https://security-tracker.debian.org/tracker/)
   and retain [the original scan summary](evidence/gcp-owner-2026-11-16/scan-comparison.json).
   The [completed reconciliation](evidence/debian-image-remediation-2026-11-16/debian-triage.json)
   confirms all 40 pairs are open and records no Debian 13 fixed versions.
2. **Qualify the base image candidate.** Build the candidate with Podman on Linux amd64
   and verify pinned build inputs. The current `Containerfile` starts the local
   entrypoint. Set the Cloud Run container command and arguments explicitly to
   run `week2.cloud_app`; test those same arguments in CI. Repeat six offline
   workflows, the IAP route checks and the SBOM/scan with its detection control.
   The pinned Wolfi candidate passed locally and the committed recipe passed
   [hosted verification](https://github.com/rajesamp/CRA2/actions/runs/43996182031).
3. **Prepare the runtime configuration.** Supply durable, access-scoped memory
   and audit adapters and bound telemetry retention. Verify writes survive a
   restart, authorized state is visible across two instances in a test, and
   unlisted identities cannot read or write it. Prepare a dedicated runtime
   service account, verified IAP public-key and storage egress allowlists, and
   write-once retention for privileged actions. Keep project identifiers,
   OAuth credentials and the owner email in private configuration. Review the
   resource and IAM changes together with their cost estimate before applying.
   See the [durable storage configuration and live checks](cloud-durable-storage.md).
4. **Sign and deploy the final image with owner access.** Rebuild with the runtime
   changes and repeat the checks from step 2. Publish the passing image to
   Artifact Registry, sign it, and attach SLSA build provenance. Verify the
   signatures and attestations for the exact registry digest Cloud Run will use.
   Enable direct IAP with the
   invoker IAM check enabled, grant the IAP service agent service-level invoke
   access, and grant IAP access to the owner. Verify effective inherited IAM as
   well as service bindings. Confirm the required OAuth audience and exact
   signed-header audience in the target project. Begin with local evidence mode,
   provider calls disabled, request-based billing, zero minimum instances and
   one maximum instance for owner testing. Validate resource sizing and bounded
   chat admission, request timeouts, and the spend stop procedure against the
   $10/month planning target. [IAP setup](https://docs.cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run)
5. **Verify and hand off the URL.** Check revision readiness, owner sign-in,
   signed-out and unlisted-account denial, the direct URL, queue and reconnect
   behavior, six demo intents, and restart persistence. Record the digest,
   revision, owner walkthrough results, duration and billed usage estimate.
   Stop on an authentication, data access, or persistence failure, or when the
   test spend limit is reached. For the first revision, verify a stop procedure
   that cuts off access while preserving evidence and state. Once a known-good
   revision exists, verify traffic rollback and state compatibility.
   [Cloud Run rollback](https://docs.cloud.google.com/run/docs/rollouts-rollbacks-traffic-migration)

The signed Wolfi candidate advanced to hosted CI after the local scan and
startup checks passed. The [evidence](evidence/debian-image-remediation-2026-11-16/README.md),
[updated manifest](../intent/guardrails-ci-cloud-run/release-base-v2.pinned.json)
and [validated CI selection](../intent/guardrails-ci-cloud-run/release-base-v2.record.json)
record the comparison with the exact Debian image.

⟦ verdict · sha256=1a890720e11c970f75a39da0f77c8e8be897e682f812e3153858d8f873b6c73f · level=preferred · delta=evidence ⟧

IAP login does not by itself establish team-write permission. The cloud entrypoint
now derives a stable opaque abuse identity from the verified issuer/subject, and
Gradio receives it through a server-owned authentication dependency. Signature,
issuer, exact audience, expiry and token lifetime are verified; plain email and
forwarded headers do not establish identity. The local entrypoint retains its
loopback behavior and refuses to start when `K_SERVICE` is present.
[Signed IAP identity](https://docs.cloud.google.com/iap/docs/signed-headers-howto)

`python -m week2.cloud_app` is the separate cloud entrypoint. It requires a single
`CRA2_OWNER_EMAIL`, the exact service `CRA2_IAP_AUDIENCE`, and dedicated state and
audit buckets. Only content-free `GET /healthz` bypasses authentication. HTTP
and WebSocket application routes require the verified owner identity. The cloud
entrypoint uses durable preferences and audit adapters and awaits live proof of
IAM, retention and restart behavior.

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

## C5 release identity and verification

The protected workspace displays a short release, source and dataset label from its image. A local checkout without packaged metadata displays “Local build · Release unverified”. The public intro runs a separate entrypoint with its own static version. The [dated inventory](evidence/releases/2026-11-23-inventory.json) records the observed V1 deployment, a green C3 draft and the C4 candidate. Each entry keeps the date and scope of its original evidence.

### Reproduce a candidate locally

Use a clean checkout at the intended commit, Python 3.13, the approved encoder archive, Node with Playwright and Chrome, and an existing local Podman connection. Place outputs outside the checkout. The prepare command takes files from the named Git commit, calculates full source and dataset identities, and copies only the reviewed model archive into the build cache. The container build verifies the archive, its extracted files and the resulting index against the packaged sources. It also compares the application bytes in the image with the exported source fingerprint before writing the display label.

```sh
candidate=$(git rev-parse HEAD)
evidence_dir=$(mktemp -d)
uv sync --locked --project week2 --python 3.13
uv sync --locked --project evaluation --python 3.13
week2/.venv/bin/python -m scripts.release_record prepare --source "$candidate" \
  --encoder week1/.cache/models/fast-bge-small-en-v1.5.tar.gz \
  --context "$evidence_dir/context" --out "$evidence_dir/identity.json"
week2/.venv/bin/python -m week1.setup_index
week2/.venv/bin/python -m pytest -q week2/tests week3/tests week4/tests -m 'not live' \
  --junitxml="$evidence_dir/tests.xml"
week2/.venv/bin/python -m evaluation.probe_release_browser --identity "$evidence_dir/identity.json" \
  --out "$evidence_dir/browser.json"
podman --connection "$CRA2_BUILD_CONNECTION" build --platform linux/amd64 \
  -f "$evidence_dir/context/Containerfile" -t localhost/cra2:c5 "$evidence_dir/context"
week2/.venv/bin/python scripts/check_container.py localhost/cra2:c5 --connection "$CRA2_BUILD_CONNECTION" \
  --identity "$evidence_dir/identity.json" --out "$evidence_dir/container.json"
week2/.venv/bin/python -m scripts.release_record record --source "$candidate" \
  --identity "$evidence_dir/identity.json" --out "$evidence_dir/record.json"
```

The browser probe launches the real protected app on loopback with a signed synthetic owner and disposable storage. It checks packaged, missing and corrupt metadata, then opens the anonymous intro and checks its fixed redirect. Set `CRA2_PLAYWRIGHT_MODULE` if Playwright is installed outside Node's normal module path. Container verification runs with networking disabled. A comparison with `--identity` fails if the tested image lacks the expected label.

### Record release evidence

The Week 2–4 workflow writes `release.json` with the PR head, actual checkout, run link, Python test counts, public controls and frozen retrieval evidence. A PR run may test GitHub's merge commit. When importing it, use the commit that was actually checked out to reproduce those observations. Store the redacted summary with its immutable source reference under `docs/evidence/releases/` when recording a release. The artifact retention period is 14 days. Re-running a local test produces a new observation.

The `record` command accepts an optional `--observations` JSON file. Omitted sections produce unknown or pending results. Dates use UTC, for example `2026-11-23T12:00:00Z`. Fingerprint private evidence and revision names locally with SHA-256. Keep the underlying records in authorized storage. The verifier accepts the following sections.

| Section | Input |
|---|---|
| `pr` | Full head, PR number, observation time and draft/open/merged/closed result. |
| `hosted` | Full PR head, actual checkout, workflow name `week2-4`, GitHub run number, test count, result and observation time. Copy these from the checked run. |
| `local` | Exact source, observation time, test count, passed/failed result and SHA-256 of the JUnit evidence. |
| `serving` | Capture time, evidence fingerprint and component arrays named `protected` and `intro`. Each row carries a hashed revision name, integer traffic percent and resolved registry manifest digest. Include all traffic for each component. The output retains positive shares. |
| `browser` | Observation time, evidence fingerprint, fingerprint of the accompanying traffic capture, actual serving revision fingerprint, displayed label and the three owner, anonymous and unlisted access outcomes. The field names are `at`, `evidence`, `traffic_evidence`, `revision`, `label`, `owner_allowed`, `anonymous_denied` and `unlisted_denied`. Use a null revision when the request cannot be attributed during a split. |
| `acceptance` | Exact source, bundle, date, SHA-256 of the explicit owner decision and scope (`protected-workspace`, `public-intro` or `both-components`). Earlier sign-offs cannot accept a new bundle. |

For a later authorized promotion, export the original, byte-preserving single-platform registry manifest and image config as `manifest.json` and `config.json`. Record the independent registry manifest digest and UTC observation time in `publication.json` under `manifest` and `at`. Use the existing Podman and scan procedure to produce `container.json`, `summary.json`, `sbom.json`, `scan.json` and `canary-scan.json` for that config. Keep the original files. Reserializing them changes their digests.

Supply the Cosign simple-signing payload as `image-signature.json` and the signed in-toto SLSA v1 statement as `provenance.json`. Their detached base64 signatures are `image.sig` and `provenance.sig`. The signed statement must bind the registry manifest to the full Git source via a resolved dependency with URI `git+https://github.com/rajesamp/CRA2` and a `gitCommit` digest. Use the operator's independently trusted public key. The verifier supports ECDSA/SHA-256 and RSA PKCS#1 v1.5/SHA-256 detached signatures. Historical or differently encoded evidence retains its original scope until it can be verified. Run the following from the checkout matching the image source.

```sh
week2/.venv/bin/python -m scripts.release_record record --source "$candidate" \
  --identity "$evidence_dir/identity.json" --observations "$evidence_dir/observations.json" \
  --publication "$evidence_dir/publication" --key "$CRA2_TRUSTED_PUBLIC_KEY" \
  --out "$evidence_dir/release.json"
```

Require the verified manifest, config, fresh scan, signed source and the candidate's current review and test evidence before a promotion decision. After an authorized rollout, inspect positive-traffic revisions for each component, resolve their registry digests, and tie a signed-in browser request and access checks to the same traffic capture. A label or access mismatch is recorded and returns an error. Unknown evidence leaves the corresponding verification open. The record does not change deployment, IAM, invitations or labeling.
