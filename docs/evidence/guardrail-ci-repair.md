# Guardrail and evaluation repair — 2026-11-16

The output rail accepted an affirmative authorization paraphrase. The evaluator
trusted a refusal flag without checking the displayed answer. Both are repaired.

## Verification

| Check | Result |
|---|---|
| Regression tests before repair | 26 failed, 15 passed; expected language/scorer failures |
| Complete Week 2–4 suite after repair and startup fixes | [337 passed](guardrail-ci-2026-11-16/tests.json), 160 upstream NeMo deprecation warnings |
| Development and validation | [18/18](guardrail-ci-2026-11-16/development.json), zero provider attempts |
| Corrected reserved cases | [4/4](guardrail-ci-2026-11-16/reserved.json), zero provider attempts |
| Scorer negative/positive controls | [7/7](guardrail-ci-2026-11-16/canaries.json) |
| Required-check and dependency faults | [9/9](guardrail-ci-2026-11-16/faults.json), zero provider attempts |
| Cloud Run startup arguments and temporary directory | 8 failing argument controls before implementation; 1 failing temporary-directory regression; 13/13 app tests after both fixes |
| Real HTTP startup | Explicit all-interface bind with `PORT=18763`; `/config` returned HTTP 200; process shut down |
| Nonroot Linux/amd64 container | [6/6 offline graph intents](guardrail-ci-2026-11-16/container.json); `/config` HTTP 200 on `0.0.0.0:8087`; application-file request HTTP 403; networking disabled |
| Linux dependency selection | uv locked dry run for x86_64 Linux succeeded; 145 packages resolved |
| New workflow | YAML parsed; 11 steps; contents-read permission; first GitHub run blocked on reviewed encoder mirror |

Environment: the existing Week 2 locked Python 3.13 environment on macOS.
Use the commands in `.github/workflows/week2-4.yml` to reproduce. For a local run,
unset `CRA2_ENV_FILE`, set `TMPDIR=/tmp`, disable CRA2/LangSmith/LangChain tracing,
set Hugging Face/Transformers offline flags, and clear `GROQ_API_KEY`.
Model setup verifies the pinned local encoder; CI requires a reviewed mirror URL
in `CRA2_MODEL_ARCHIVE_URL` before downloading it and running tests. The original
public archive returned upstream HTTP 403 AccessDenied from both host and Linux.
The existing 76,692,531-byte archive matches SHA-256
`3858004b3822f64f940280874b8f2d2dc25b34a4f3eb3cdf617bdceeb21ed9ed`.
The model and checksum policy remain unchanged. Runtime checks never need an
LLM-based safety classifier. No model asset has been published by this work.

The container runtime is digest-pinned distroless, user `65532:65532`. Verification
found and fixed root-only public cache modes and a Gradio temporary-directory
override. Reproduce using `scripts/check_container.py` and the commands in the
[deployment plan](../cloud-run-plan.md). The final verified local image ID is
`10ab62a5c25ff7d7b785383fdc0ade1acc7305ab95f4a701de1be1cc3a1168f9`.
This is local execution evidence, not an artifact signature or deployment pass.
The isolated Podman build VM was stopped; the original default connection and
legacy VM data were preserved. No Docker installation was required.

## Scope and limits

Runtime matching covers explicit approval, authorization, clearance and go-ahead
forms, including Markdown formatting. Immediate negation is handled separately;
a refusal elsewhere cannot cancel an affirmative grant. A graph-level regression
confirms the actual output rail discards unsafe text from the help collaborator.
The first version of that test patched the legacy responder, which the help route
does not call; the injection point was corrected without changing its assertions.

The independent scorer checks visible refusals and contradictory approvals for
both rendered evaluation outputs and the six core contracts, including separate
memory processes. A trace flag alone cannot pass. Positive controls catch a scorer
that rejects everything; negative controls catch one that accepts everything.
The existing `--canary` intentionally exits 1; CI uses `--verify-canaries`, which
exits 0 only when all seven scorer controls behave as labeled.

The scoring contract is **visible-advisory-v2**. Prior reports are unchanged and
not directly comparable. Reports contain source hashes because their Git parent
may precede the implementation commit. These are local contract regressions,
not independent semantic-safety gold labels or production/model quality estimates.
The language rules have bounded coverage. Deployed IAP, identity isolation,
persistence, capacity and supply-chain security controls remain separate gates.

The caller's pre-existing documentation edits were not included in the repair or
CI commits. No push, cloud provisioning, provider invocation or deployment occurred.
Owner acceptance is pending. No prospective-user access grants or invitations may
occur until the owner finishes testing and explicitly approves them.
