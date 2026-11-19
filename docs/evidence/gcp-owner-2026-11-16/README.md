# GCP owner-access implementation evidence

Observed 2026-11-16. **Implementation milestone complete; release blocked.**
No Cloud Run service or output image was published. No prospective-user access
grants or invitations were made. Owner acceptance remains pending.

## What is implemented

- A separate `week2.cloud_app` entrypoint validates signed IAP assertions and
  admits only the configured owner. It rejects plain email/proxy headers,
  invalid signatures, wrong audiences, expired tokens and other identities.
- Cached Google public-key retrieval has bounded input, refresh/backoff and
  failure handling. Unknown/unusable keys fail closed. Required tests include
  real ES256 signatures and key rotation; they do not establish live Google IAP.
- The real Gradio mount receives an opaque verified principal through its auth
  dependency. HTTP and WebSocket paths are protected before app handlers.
  Only content-free `GET /healthz` bypasses authentication.
- A Podman CI workflow inventories the exact tested image with Syft and scans
  with Grype. Tool downloads are pinned by size and hash; publisher checksum
  signatures are verified with pinned Cosign and exact publisher identities.
- Scan validation rejects incomplete/empty inventories, missing application
  packages, wrong image identities, stale/invalid databases and filtered reports.
  High, Critical and Unknown findings block release, including suppressed matches
  and findings without fixes. A metadata-only Django 1.2 canary proves detection.

## Automated evidence

| Check | Result | Artifact |
|---|---|---|
| Week 2–4 tests plus Week 1 retrieval compatibility | 430 passed; 160 dependency warnings | [Tests](tests.json) |
| Development and validation | 18/18; provider attempts 0 | [Cases](development-validation.json) |
| Corrected reserved cases | 4/4; provider attempts 0 | [Reserved](reserved.json) |
| Independent scorer controls | 7/7 | [Canaries](canaries.json) |
| Injected dependency, capacity and required-check faults | 9/9; provider attempts 0 | [Faults](faults.json) |
| Linux/amd64 nonroot Podman image, network disabled | Six real workflow intents passed; HTTP 200; application file 403; four unsigned cloud paths 401 | [Container and source hashes](container.json) |
| Embedding library update | Identical vectors for 11 corpus passages and six queries; original artifact checksums verified | [Parity](encoder-parity.json) |
| Tool publisher signatures | Syft, Grype and Cosign verified | [Pinned tools](supply-chain-tools.json) |
| Distroless input signatures | Runtime and builder verified | [Coverage and outstanding signatures](base-signatures.json) |
| Release scan/control | Correctly blocked; known-vulnerable canary detected | [After](scan-after.json), [before](scan-before.json), [comparison](scan-comparison.json) |

Tests use `TMPDIR=/tmp`, no `CRA2_ENV_FILE`, tracing disabled and model providers
disabled. A first invocation using macOS's default temporary directory was
rejected by the existing private-store path policy. Following the library update,
two tests correctly rejected the old index fingerprint. Rebuilding the synthetic
index through `week1.setup_index` produced the final all-pass suite. CI already
performs that index setup before testing.

## Security updates and remaining scan findings

The release lock now uses Brotli 1.2.1, certifi 2026.10.23, Gradio 6.32.0,
FastEmbed 0.9.1 and Pillow 13.0.0 on Python 3.13. Gradio's bundled
`follow-redirects` is 1.16.3 in the rebuilt SBOM. Only those five Python package
versions changed. The original encoder archive and extracted file pins remain
unchanged. The encoder fingerprint deliberately includes the library version,
so the synthetic index must be regenerated after this update.

[Brotli advisory](https://github.com/advisories/GHSA-9v8h-qqgm-4m35),
[certifi advisory](https://github.com/advisories/GHSA-6q48-6c7w-9gw2),
[Pillow advisory](https://github.com/advisories/GHSA-w889-685w-c8fh).
Compatible dependency bounds were checked against publisher metadata for
[Gradio 6.32.0](https://pypi.org/pypi/gradio/6.32.0/json) and
[FastEmbed 0.9.1](https://pypi.org/pypi/fastembed/0.9.1/json).

Python 3.10 remains a local compatibility target and resolves older Pillow;
**it is not a release-image target**. The container uses Python 3.13. The new
constraint requires patched Pillow on Python >=3.11. The new GitHub jobs have not
run; no Python 3.10 CI pass is claimed here.

The final SBOM contains **162 packages**. The scan reports 312 matches, including
**104 release-blocking matches across 20 Debian packages**: 4 Critical, 71 High
and 29 Unknown. No blocking Python/npm matches remain in this collected image.
The database lists no fixed versions for those 104 Debian matches. These include
multiple package matches and advisory aliases, not 104 proven exploit paths.
No exception or ignore rule was added to make the release pass. Both scans used
the database built at `2026-11-16T06:30:54Z`; the detection control found 27
High/Critical matches for deliberately vulnerable metadata.

Raw local SBOM/scan reports include host configuration paths and are not committed.
The bounded summaries retain their SHA-256 values and immutable image binding.
The current local OCI archive is `/tmp/cra2-gcp-security.oci`; the scan reports
are in `/tmp/cra2-release-scan-after/`. The independent build VM was stopped after
verification; its original default connection was preserved.

## GCP and cost state

[Preflight](gcp-preflight.json) confirms configured authentication, project access
and billing enabled. The Cloud Billing API was enabled on the target project to
complete that read, using the explicit target quota project. Actual cloud IDs,
emails and region remain in ignored local files.

The monthly planning amount is USD 10, assuming USD. The
[budget calculation](budget.json) and [cost note](../../cloud-run-budget.md)
separate 1,000 registered users from 1,000 daily active users and state the omitted
costs. No cloud budget, cap, quotas or resource limits were applied.

## Remaining deployment gates, in order

1. Resolve or substantiate the Debian base findings under the required release
   policy, then regenerate image-bound test and scan evidence. This scan blocks
   deployment; signatures do not override vulnerability findings.
2. Supply an approved reachable mirror of the exact encoder archive. The upstream
   URL returns 403. No public release asset was published and the repository
   mirror variable was not configured. Both new CI paths require it.
3. Complete output image signing and SLSA provenance, verify the remaining build
   input, and test an immutable release digest. No output signature is claimed.
4. Implement durable memory/audit, explicit write authority, retention, shared
   admission limits and user isolation. Current `/tmp` SQLite is a smoke-test
   arrangement, not deployment storage.
5. Prepare the concrete least-privilege IAM, external OAuth, default-deny egress,
   runtime limits and cost-control configuration. Do not apply an irreversible
   audit retention lock without its own concrete approval.
6. Deploy for the owner, test real Google sign-in, denied identities, alternate
   ingress, queue/stream behavior, restart, load and rollback. Record owner tests.
7. Only after owner acceptance and later explicit approval, plan invitee access
   bindings and separately authorized invitations.
