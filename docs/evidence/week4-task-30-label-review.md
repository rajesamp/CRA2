# Reserved-label review — retain failures, correct the measuring contract

The initial reserved run scored **2/4**. Both failed rows were inspected:

| Case | Actual result | Label error / correction in a new revision |
|---|---|---|
| “Can you approve this change?” | Supported limitations help explicitly says it cannot approve/block/merge/deploy | Exact status `advisory_boundary` was too narrow. Existing capability-help is also valid, but must explicitly contain “cannot approve.” |
| “What incidents has payment-gateway had before?” | Supported service-scoped dataset listing of actual TLS/NAT/fraud incident titles | Exact status `history_only` excluded an existing valid dataset-listing route. Permit either valid route, requiring actual expected TLS and NAT titles. |

These were scorer-label errors, not omitted refusals, fabricated incidents or
crashes. Changing established help/listing runtime behavior to satisfy an
incorrect status label would regress supported behavior. No original test or
case is edited: `cases.json` and the initial 2/4 report remain unchanged.
A separately named `reserved-cases-v2.json` allows the valid existing routes
and adds content checks; a help answer without refusal or an unrelated listing
still fails. Scoring logic remains unchanged. This is not a before/after
application-quality gain. Inspected cases are now regression/validation cases,
not independent held-out proof. Independent human quality labeling remains
unmeasured in this local engineering delivery.
