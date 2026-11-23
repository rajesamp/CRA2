# Show the size of the proposed change

**Draft for owner review · November 23, 2026.** A reviewer should see how far a setting moves and how much of the deployment is known to change. These are different quantities. A one-line timeout edit can change a value by 90% while the number of affected deployments remains unknown. DORA’s batch-size guidance concerns how much work ships together. Its change fail rate requires observed deployments and outcomes. [DORA metrics guide](https://dora.dev/guides/dora-metrics/)

## What changes

Chat already normalizes timeout units, calculates a percentage for an unambiguous positive pair and reports retry counts. Expose those facts in a reusable **Change size** section, with original values, units, signed difference, and a source reference to the current proposal. Use the same calculation for chat and the review view. A second row describes deployment scope. Count only distinctly identified, explicitly changed services or deployable items of the same kind. Label a declared target as such. Mark scope partial or unknown unless the input covers the full change. Dependencies and related incidents cannot establish that count. [Current calculation](https://github.com/rajesamp/CRA2/blob/3308ab23e0dac3d23ba7e189b98deaca92bed54b/week2/presentation.py) · [Existing regression cases](https://github.com/rajesamp/CRA2/blob/3308ab23e0dac3d23ba7e189b98deaca92bed54b/week2/tests/test_useful_answers.py)

For “change checkout-service timeout from 4 s to 400 ms,” show **4,000 ms → 400 ms · 3,600 ms shorter · 90% decrease**. The proposed timeout is one tenth of the original. Show **1 named target service · total rollout scope unknown** when checkout is the only target supplied. Both rows describe the proposal. The result supplies no risk rating.

## Calculation and acceptance on Python 3.13

| Fixture | Expected result |
|---|---|
| 4 s → 400 ms, then 400 ms → 4 s | −3,600 ms and −90% in the first direction. +3,600 ms and +900% in the reverse. Percentages use the original value as denominator. |
| 1 s → 1,000 ms | An unchanged value after unit conversion. |
| 0 ms → 400 ms | Show the supplied values. Relative change is undefined. Ask how zero is interpreted by this service. |
| Retries from 2 to 4 | Two more configured retries. Observed traffic amplification remains unknown. |
| A value missing, incompatible units, an unsupported setting, or multiple ambiguous pairs | Ask for the setting and one comparable before/after pair. Suppress the unsubstantiated calculation. |
| One declared target service with three catalog dependencies | One named target. Dependencies remain separately attributed exposure. Repeated mentions of the same service count once. |
| A user edits the timeout, or two signed users submit different changes | Recompute from the admitted active proposal. Expired, blocked or cross-session inputs yield no stale value. |

Use bounded decimal parsing and round only for display. Keep the existing uncertain-input handling and regression examples when sharing the calculation. Review summaries can supply a typed handoff in a future integration with guided intake. PR #32 currently forwards service and summary to chat. No repository diff reader, file upload or external model is required for this slice. [Guided-intake handoff](https://github.com/rajesamp/CRA2/blob/434f8bc182a9b82a6a0e1bd51420e0bf7c3fdeb4/week2/intake.py#L96)
