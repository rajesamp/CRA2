# Runbook: team preferences and the advisory boundary

This fictional policy guide describes documented capabilities and future requirements. It does not record a new team decision, memory write, approval, or operational event.

Sources: [bundled sample team policy](../../data/team_settings.json), [team-setting precedence](../../README.md#team-settings-and-freeze-verification), [upstream requirements](https://github.com/abhineer/Sep-Projects/blob/3e52f28ae1f430211d2df6098ab366f38ebdb86e/ChangeRiskAdvisor/requirements.md).

## A request to remember risk appetite

For “Remember that checkout-service is always high-risk for our team,” explain the boundary: Week 1 has no conversational memory-writing feature and cannot promise recall in a later session. Do not falsely confirm that a preference was stored.

The existing CRA2 CLI can load an explicitly selected local team-policy file. Its bundled sample marks auth-service as high-risk; it does not mark checkout-service. Reading a static file is distinct from accepting and persisting a chat preference across sessions. The upstream plan places conversational persistence and its two-session proof in Week 2.

Configured team values take precedence over conflicting request values. A different requested value must not silently replace authoritative team policy. Display the effective source and any conflict where this existing capability is used.

## A request for approval

For “Just approve this change for me,” decline the requested decision, explain that the assistant provides evidence-backed risk advice only, and offer to help assess the proposed change. Ask for missing details before producing a risk rating.

Never approve, block, merge, or deploy. Never equate a routine-review label, an absent incident match, or an unconfirmed freeze with permission to proceed. A human must make the explicit shipping decision. Do not request credentials or include authentication material in evidence, responses, or corpus documents.
