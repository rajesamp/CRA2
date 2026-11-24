# Implementation plan for risk by category

**Draft for owner review · November 23, 2026.** The owner approved the three V2 specs in `c6a4f7b`. This plan covers the risk categories in the signed-in **Incidents & rollback** review. The change-size and rollback-checklist specs have separate implementation plans pending. [Approved risk spec](risk-categories.md)

## What the owner will see

A completed checkout timeout review shows four cards in a fixed order. Each card answers “What do we know?”, “Where did that come from?” and “What should I check next?”

| Card | Expected checkout result | Question |
|---|---|---|
| Technical | List the three direct dependencies from the checkout service’s `depends_on` field. | Which calls use the timeout being changed? |
| Operational | Cite the checkout `monitors` field for p99 latency and error rate. The snapshot has no observation date, so show **Freshness unknown**. | Which threshold and observation window would stop the rollout? |
| Business | **Evidence gap** for customer exposure. Service criticality and a payment monitor alone cannot establish customer or financial impact. | Which customer journey and measure will the owner check? |
| Security and compliance | **Evidence gap** for access and data handling. A dependency on authentication alone cannot establish a policy change. | Does this proposal change a protected boundary or the classification of data it handles? |

## Build sequence

1. **Pin the examples and failure cases.** Add deterministic fixtures to `week2/tests/test_incident_rollback.py` using the existing checkout catalog, a fixed date, and temporary source copies. Cover the four cards above, a removed optional field, missing required evidence, a mismatched citation version, and an operator’s freeze declaration that conflicts with the catalog. First show that the existing successful result lacks the category section.

2. **Build the citations from the evidence used by that review.** In `week2/incident_rollback.py`, extend `analyze` to assemble bounded category data from the validated service record, selected incidents and accepted form fields. Bind a citation to its source type, service, field or incident ID, and evidence version. Compute a deterministic version from the exact validated source values used for the review, including selected incident IDs and values, using the canonical digest in `week2/release_info.py`. Keep declarations scoped to the active review ID. The existing callback creates that ID before analysis. Pass it into the guarded path before building the report. Preserve existing calls to the analysis helper by accepting an optional review ID and generating a fresh one when absent. Reference resolution uses only that review’s captured data, with no second catalog read or lookup across sessions. Display human-readable references such as `catalog:checkout-service.monitors`. A compact version may be shown while the full digest is used for equality. A package release label or the review date alone cannot establish a source version.

3. **Apply the four category rules.** Use a fixed category order and bounded, deterministic templates. Distinguish recorded catalog fields, historical analogues and unverified declarations. Keep each finding beside its reference, with observation date or unknown freshness. Keep both sources for a disagreement and ask how to resolve it. An absent optional field or a reference that fails to resolve drops that claim. If the category then has no evidence, show the gap and one concrete question. Preserve the existing unavailable outcome for invalid required sources. Use gaps for business and security whenever the admitted fields cannot substantiate those categories. The feature adds no risk or success score, automatic approval, provider call or dataset write.

4. **Render inside the checked recovery report.** Assemble all source-derived card values before `guarded_analyze` passes the report to NeMo’s context check. Extend `render` with semantic headings, escaped text and plain source references. Pass the complete HTML through the existing output check once. In `week2/app.py`, deliver only those checked bytes after the required stage receipts and telemetry write succeed. Keep the audit record’s current field allowlist. A blocked or unavailable review shows the existing withheld result, including when a prior successful report was visible.

5. **Invalidate on edit and late completion.** In the seven recovery form controls in `week2/app.py`, advance a form revision and clear the visible report as soon as an input changes. Bind each submission to its session, form revision and server-issued review ID. Release a completed result to the current view only when it still matches the latest submission in that session. Enforce this at delivery so an older queued response cannot repaint the page after an edit or a newer submission. An edit followed by a change back to the same text still invalidates the old submission. Discard the session marker on expiry. Keep review text out of the invalidation state. Use the existing protected callback, identity checks and shared queue. The public intro has no category component.

## Python 3.13 verification

From the repository root, prepare the locked Week 2 environment and the checksum-verified encoder and synthetic index using the setup in the [Week 2–4 workflow](../../.github/workflows/week2-4.yml). During the tests use its offline settings, empty provider key, disabled tracing and local storage fixtures. These commands are for the implementation stage.

```sh
uv sync --locked --project week2 --python 3.13
week2/.venv/bin/python -c 'import sys; assert sys.version_info[:2] == (3, 13)'
week2/.venv/bin/python -m pytest -q week2/tests/test_incident_rollback.py week2/tests/test_audit_correlation.py week2/tests/test_capacity_mount.py week2/tests/test_landing.py
week2/.venv/bin/python -m pytest -q week2/tests week3/tests week4/tests -m "not live"
```

| Exercise | Passing evidence |
|---|---|
| Grounding and repeatability | All four cards appear once. Every factual claim resolves to the expected field or record in the active version. The fixture produces two explicit gaps. With review ID, date and sources fixed, two runs produce identical cards and the provider spy records zero calls. |
| Removed, changed or conflicting evidence | Remove optional monitors and the operational monitor claim disappears. Change a selected value under the same field name and the old version fails resolution. Corrupt a required source and the review is withheld. A freeze disagreement preserves both attributed values and a verification question. Historical matches stay labeled as history. |
| Required safeguards and output bounds | Exercise denied admission, blocked nested evidence, missing NeMo stage receipts, output rejection and an unavailable telemetry write. Each shows zero cards or seeded private strings. A normal report displays exactly the HTML checked by the output rail. Verify markup escaping and that oversized evidence follows the existing fail-closed size limits. Inspect the fixture audit record for its allowed metadata only. |
| Signed browser and public intro | Extend the loopback signed-browser fixture used by `evaluation/probe_audit_browser.py` and the recovery UI driver in `evaluation/answer_browser.cjs`. Use two isolated browser contexts with synthetic owner sign-in and distinct session markers. Submit different changes, edit one while its response is held, then release it. Repeat with a newer submission already visible. Each session shows only its latest result. Replacing a successful review with a blocked one clears the cards. Anonymous access to the protected app is denied. The public intro and sign-in redirect expose zero markers or findings. |

Add a targeted runner at `evaluation/probe_risk_categories_browser.py`. Run `week2/.venv/bin/python -m evaluation.probe_risk_categories_browser` with local Chrome, Node and Playwright configured as for the existing browser driver. It must exit nonzero on a failed or unobserved case.

Add the focused tests to existing pytest discovery. Keep the Week 2–4 workflow’s C1 guardrail counts, C2 capacity checks, C3 public controls, fault injection, offline TruLens checks and release verification. Record the tested commit, interpreter version, fixture cases, pass/fail counts and browser observations without raw inputs or identities. Distinguish local browser evidence from hosted CI. The implementation requires a passing signed-browser run as well as the Python suite.

## Approval boundary

This draft is ready for plan review. Implementation starts after plan approval. Testing uses synthetic local identities and fixtures. The Cloud Run app stays owner-only. Invitations and independent labeling remain on hold.

## Implementation record

The owner authorized local implementation on November 23, 2026. The first regression failed because a successful checkout report lacked the category section. The citation rules are in `week2/risk_categories.py`. The request and source snapshot are passed through the existing recovery guardrails and telemetry contract. `week2/recovery_view.py` binds the checked response to the originating form submission and invalidates it on edits. The capacity callback inventory includes the private browser receipt handler. Both the normal protected mount and the local capacity mount use the same display rule.

The signed browser probe uses the existing local server and public-intro fixtures alongside `evaluation/risk_categories_browser.cjs`. Its two browser contexts check the visible result and replay a delayed delivery carrying its original receipt. The dedicated driver leaves the existing single-input evaluation driver available for its original checks.
