# C1 implementation plan · Screen retrieved evidence before use

**For owner review.** The owner approved the [C1 spec](spec.md) at commit
`d6a848528d4cef9ff8de268d87860472b01c8c13` on 2026-11-22, including
“withholding quoted instructions that match the guardrail.” This records spec
acceptance. Implementation starts after owner review and acceptance of this plan.
The protected app stays owner-only and invitations remain on hold.

## Files that change

| Files | Planned change |
|---|---|
| [week3/guardrails.py](../../week3/guardrails.py) | Validate the context batch before the engine receives it. Screen original and normalized field values inside the real NeMo action. |
| [week1/chat.py](../../week1/chat.py), [week1/answers.py](../../week1/answers.py) | Separate local source selection from answer and trace construction for delegated chat and dataset browsing. Preserve the synchronous Week 1 entry point. |
| [week2/workflow.py](../../week2/workflow.py) | Await one context verdict per selected batch before downstream use on normal and delegated chat paths, including cache reads. |
| [week2/incident_rollback.py](../../week2/incident_rollback.py) | Screen decoded values selected for the recovery report. Release the exact rendered output that passed the output rail. |
| [week3/tests/test_guardrails.py](../../week3/tests/test_guardrails.py), [week3/tests/test_cache.py](../../week3/tests/test_cache.py) | Exercise the real action, fixed case inventory, failure states, size limits and per-request cache checks. |
| [week2/tests/test_workflow.py](../../week2/tests/test_workflow.py), [week2/tests/test_incident_rollback.py](../../week2/tests/test_incident_rollback.py), [week2/tests/test_welcome_identity.py](../../week2/tests/test_welcome_identity.py) | Check downstream call order, marker absence at each sink, original evidence on success and isolation in the mounted app. |
| [.github/workflows/week2-4.yml](../../.github/workflows/week2-4.yml) | Validate the presence and counts of C1 results in the existing JUnit artifact on both supported Python versions. |

## Order of work

1. **Commit the regression first.** Run the existing focused baseline. Add tests
   against the public interfaces, using synthetic data and harmless markers.
   Show a failing assertion for the reported matching or ordering behavior on
   the accepted revision. Record the test ID and observed result in the test-only
   commit. An import failure, missing encoder or external service cannot count
   as that result. CI fixtures must work from a clean checkout.
2. **Enforce the batch contract (R1, R2, R4).** Reuse
   [checked and MAX_JSON](../../week2/contracts.py). Validate shape, credentials
   and serialized size of the original batch before calling the engine. Bound
   the derived screening batch by the same 65,536-byte limit. For each decoded
   prose value, including a hit's title and body, match both the original and
   the spec's normalized copy. A match anywhere withholds the whole batch.
   Preserve field boundaries, references, ranking, casing and original display
   text. Keep the mapping from the action's verdict and engine status to the
   existing event codes. A verified match emits `block / untrusted_context`.
   If a required check starts but fails without a verdict, record one
   `unavailable / rail_unavailable` event. A preflight or source error may stop
   the flow before NeMo runs.
3. **Move the check to the point of selection (R3, R4).** Split Week 1's
   response path into early answers, source selection and composition. Week 1's
   synchronous wrapper still drives those stages. The Week 2 legacy node awaits
   the context rail on the selected values, then hands the same selection to
   composition. Keep one lookup per request and preserve history/service
   resolution. On the main graph, validate after fresh retrieval or cache read
   and before tools, evidence-based composition and any reviewer invocation.
   A failed check takes the static fallback path.

   In dataset browsing, the current trace has an empty `retrieved` list even
   when the response contains source fields. Separate selection in
   `_dataset_titles` from rendering. Screen selected titles and source-derived
   values destined for either the answer or its scenario trace, including on
   counts that carry scenario metadata. Keep source-hash checks and the existing
   count, grouping and filter semantics. Static help still takes its early exit.
4. **Guard recovery output (R2–R4).** Keep admission, input checks, bounded
   selection and source validation. Screen decoded string values from the
   selected report, including nested incident fields, recorded rollback text
   and graph labels. Bound the report and its screening projection. After
   context passes, render once and check that HTML. Return it with the
   associated report only on verified output. For either failure, return the
   existing safe response and permitted verdict metadata.
5. **Verify the boundaries together (R3–R5).** Exercise the mounted app with
   local synthetic principals, inspect the returned trace and report, capture
   what is passed to telemetry/export, and inspect the session panel. Add the
   C1 evidence check to both CI matrix legs. Record the implementation commit,
   runtime versions and counts with the build result. If a code change departs
   from this plan, update the plan in the same commit.

## Risks

- **Highest implementation risk: delegated chat ordering.** A second lookup
  could change which records were checked, and a post-composition check could
  hide an earlier use. Assert the ordered calls and identity/content of the
  selected evidence through normal entry points. Keep Week 1 callable without
  importing NeMo or starting another event loop.
- **False blocks and changed citations.** The approved policy intentionally
  withholds full matches inside quotes. Test neutral quotations, Unicode names
  and fields adjacent in a report. Screen a temporary copy and pass original
  values to existing renderers. Preserve their escaping and citation formatting.
- **Misleading success on failures.** A source failure, an unavailable rail
  and an executed policy block have distinct meanings. Exercise each path and
  a successful empty selection. Preserve real call accounting, including an
  output check on a safe fallback where applicable.

## Proof

| Spec | Build acceptance evidence |
|---|---|
| R1, R2 | Use the actual NeMo action on a fixed, named inventory covering the [baseline](context-probes.json) (three must-block, one must-allow), an attributed full match, neutral quotations, wrapped prose and multilingual names. Exercise titles, bodies, mixed batches in both orders and separate benign fields. Verify original accepted values, IDs and citations at the consumer. |
| R3 | Record the order of selection, context verdict, composition, rendering and dependent calls. Exercise graph chat, delegated history, dataset listing/count and recovery. For a blocked or unavailable batch, count zero uses of the candidate by the answer composer, success renderer, reviewer or dependent tools. Test a cold read and an actual warm retrieval-cache hit with a fresh verdict for each request. |
| R4 | Cover malformed records, exact and over-limit serialized sizes, expansion past the limit, missing or inconsistent engine verdicts and engine exceptions. The gate withholds evidence in each failure case. A valid payload at the limit remains eligible. Static help, empty results and benign evidence retain their specified outcomes. |
| R5 | Put a unique synthetic marker in the candidate source for a rejected request. Assert its absence from the answer, structured report, trace, captured telemetry/export and rendered activity. Run two sessions for one test owner, then two test principals reusing one browser session label. Only the originating session sees the event. Verify condition and execution labels for both block and unavailable. |

Use the existing [Week 1 compatibility suite](../../.github/workflows/week1.yml)
and Week 2–4 CI on Python 3.10 and 3.13 with provider calls disabled. In the
guardrail test, check the complete set of expected case IDs, reject duplicates
or missing verdicts, and record two explicit fractions as JUnit suite properties:
missed blocks / must-block cases and false blocks / must-allow cases. Each matrix
leg must have both properties, positive denominators and zero errors. Keep the
two baseline misses visible in the historical evidence. Plan approval authorizes
the first C1 test commit; deployment, invitations and C2 are separate steps.
