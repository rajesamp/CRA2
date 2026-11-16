# Plan: guardrails, evaluation, CI and Cloud Run sequence
Input: spec.md; implementation authorized by the current user instruction.

## Files that change
- week3/guardrails.py, week3/tests/test_guardrails.py: output approval regression.
- week4/evaluate.py, week4/tests/test_evaluate.py: independent display scoring.
- .github/workflows/week2-4.yml: offline tests and evidence gates.
- week2/app.py, week2/tests/test_app.py: explicit container bind/port contract
  and a writable, deployment-configured Gradio temporary directory.
- Containerfile, .dockerignore: digest-pinned distroless runtime and allowlisted
  build context; verify with the user's Podman runtime before release.
- scripts/check_container.py: reproducible offline graph and HTTP verification
  of the exact local image ID, with temporary containers cleaned up afterward.
- docs/cloud-run-plan.md and docs/evidence/guardrail-ci-repair.md: sequence and proof.
- intent/guardrails-ci-cloud-run/: audit artifacts and decision manifests as needed.

## Order of work
1. Commit failing security/scorer regressions, recording their expected failures.
2. Fix both contracts, run focused tests, then all Week 2–4 tests and scorecards.
3. Add CI for locked dependencies, pinned model setup, tests, evaluations,
   canaries and faults. Validate syntax and run the same commands locally.
4. Implement/test Cloud Run bind/PORT support. Inspect remaining deployment
   requirements and pin any architecture decision under HERMETIC VERDICT.
5. Prepare the next concrete deployment step; record actual infrastructure or
   access blockers without presenting a local pass as deployment evidence.

## Risks
Language matching is bounded and can misclassify untested wording. Explicit
negative controls and independently written eval patterns reduce shared errors.
Changing the scorer requires a new scoring contract; historical reports remain
historical. CI and image builds require Linux evidence. Shared state and proxy
identity must be addressed before multi-instance deployment.

The user refined the access requirement to invited Google accounts only. The
fresh-context IAP decision and validation harness are recorded alongside this plan.
The existing Podman CLI is 5.0.2, while its saved VM uses the unsupported QEMU
provider. Preserve that VM and its data while preparing an independent build VM.

Build discovery: the pinned Qdrant archive URL now returns upstream HTTP 403
AccessDenied, including from the Linux VM. Preserve the existing encoder and its
hashes. Verify the locally cached archive for the container proof; clean CI needs
a reviewed reachable copy of that exact build asset before its first green run.

The owner explicitly approved publishing the verified build asset. Publish the
original bytes with checksum, provenance and upstream license sidecars; verify
anonymous download into a fresh cache, set the shared CI mirror variable, then
record actual GitHub test results. This approval does not release the invitation
hold or approve an application deployment.

Nonroot container verification found two permissions defects: index/tokenizer
files inherited root-only modes, and app import overwrote the writable Gradio
temporary directory. Make only the public model cache readable and preserve the
operator-provided temporary directory; retain the workspace-local default.

Release gate: no invitations, messages or prospective-user access grants until
the owner finishes testing and explicitly approves inviting users.

The user permits Streamlit when it simplifies delivery. The separate immutable
UI-framework manifest adds that option and records the fresh-context assessment.
No UI migration has been performed: hosting capability alone does not show that
it removes a current blocker. Revisit with the recorded comparison test if a
framework-specific problem appears or the user explicitly requires Streamlit.

## GCP implementation continuation

1. Read configured project/auth/billing/API state without provisioning resources.
2. Add failing tests in week2/tests/test_iap.py and test_cloud_app.py. Implement
   week2/iap.py, week2/cloud_app.py, the trusted identity hook in week2/app.py,
   and direct locked dependencies in week2/pyproject.toml and uv.lock.
3. Verify signature failure, owner-only admission, protected routes, key rotation,
   key-fetch failures, real Gradio mounting and local-startup separation.
4. Add the release-image SBOM/scan gate and its negative controls in scripts/
   and .github/workflows/. Pin supply-chain tools and record actual scan results.
5. Prepare the USD 10 budget/resource configuration and required deployment
   evidence. Do not grant prospective invitees access or send messages.

Owner-only authentication is an implementation milestone, not a substitute for
the remaining durability, cost, supply-chain and deployed-browser gates.

## Proof
Red/green regression output, full Week 2–4 suite, 18 development/validation cases,
four corrected reserved cases, negative scorer canaries, nine injected faults,
and startup-contract tests. Store report hashes and exact commands in evidence.
