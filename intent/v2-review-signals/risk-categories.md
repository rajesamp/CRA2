# Review evidence by risk category

**Draft for owner review · November 23, 2026.** Proposed for the protected CRA2 workspace. The reviewer should be able to answer “What supports this concern, and what do I still need to check?” for four categories. Atlassian documents the same four categories. The CRA2 proposal adds source-level attribution and an explicit gap wherever the local evidence runs out. [Atlassian product announcement](https://community.atlassian.com/forums/discussion/3310277/prevention-center-is-now-in-open-beta-new-risk-categories-for-ai-change-risk-assessment)

## What changes

The recovery prototype already returns incident references, recorded dependencies, operator declarations and unresolved checks. Group that admitted evidence in the existing review result. Use the active review ID and evidence version. Each category shows a finding, its source type and reference, and one question the reviewer can act on. A category with no applicable source reads **Evidence gap** and names the missing fact. [Recovery report](https://github.com/rajesamp/CRA2/blob/3308ab23e0dac3d23ba7e189b98deaca92bed54b/week2/incident_rollback.py) · [Source inventory](https://github.com/rajesamp/CRA2/blob/3308ab23e0dac3d23ba7e189b98deaca92bed54b/data/README.md)

| Category | Example for a proposed checkout timeout reduction |
|---|---|
| Technical | The recorded checkout catalog lists payment, inventory and authentication dependencies. Cite the service’s dependency field. Ask which calls share the changed timeout. |
| Operational | The catalog lists checkout p99 latency and error rate as monitors. Cite the monitors field. Ask for the rollout threshold and observation window. |
| Business | **Evidence gap.** Customer volume and financial exposure are unknown. Ask which customer journey and measure the owner will check. |
| Security and compliance | **Evidence gap.** No applicable access-control or policy evidence has been supplied. Ask whether a protected boundary or data classification changes. |

A catalog field is attributable to its snapshot. Use its observation date when available and display unknown freshness otherwise. Distinguish a reviewer declaration from a recorded fact and a historical analogue from a current observation. Conflicting sources retain their references and show a question to resolve. A service tier alone cannot substantiate lost revenue or a compliance conclusion. The 16 synthetic incidents and 30 sanitized samples lack a successful-deployment denominator. Category output therefore carries no failure percentage, success score or automatic approval.

## Acceptance on Python 3.13

- In the checkout fixture, render all four cards. Every factual statement resolves to its specific admitted source in the same evidence version. The two unsupported categories show explicit gaps.
- Remove a source or change its version. Its claim disappears or becomes a gap. A guardrail block or a required-check outage preserves the existing withheld response. No card exposes a blocked excerpt.
- Feed conflicting declared and recorded facts. Both attributions remain visible. Running the same fixture twice gives the same cards and zero provider calls.
- Exercise two signed local sessions. Each sees only its own current result. Editing a proposal invalidates the earlier cards. The anonymous intro exposes neither findings nor review inputs.

This is a review-display change. Existing intake, queueing, evaluations and NeMo enforcement remain the entry conditions. Owner-only access, the invitation hold and the independent-labeling hold apply.
