# Runbook: verify freeze-window and service-health claims

This is a fictional verification guide based on a static example catalog and CRA2's documented boundaries. It is not a live health check or a current freeze calendar.

Sources: [synthetic catalog snapshot](../../data/checkout_system.json), [freeze verification policy](../../README.md#team-settings-and-freeze-verification), [upstream requirements](https://github.com/abhineer/Sep-Projects/blob/3e52f28ae1f430211d2df6098ab366f38ebdb86e/ChangeRiskAdvisor/requirements.md).

## Answering “Is this a freeze window right now?”

Week 1 has no current-health or freeze-window tool. It therefore cannot confirm the current state. A historical catalog flag, incident date, or stored preference is not a current check. Ask which service and deployment window are relevant and direct the reviewer to their authoritative source of current policy.

The fictional catalog reports freeze flags for auth-service and mobile-frontend and degraded payment-gateway health. These are snapshot facts only. They must not be presented as verified present conditions.

## Recommended verification work

- Obtain an authoritative, time-stamped result for the relevant service and window.
- Determine whether the reported freeze applies to this change and whether an exception exists.
- If a source is unavailable or stale, retain an explicit unconfirmed state.
- Evaluate concrete change risks separately; an unconfirmed freeze report alone does not establish a risk score or shipping restriction.

The upstream plan schedules callable health/freeze tools for Week 2. This document does not implement those tools or simulate a successful call. Even after a future verified check, the assistant remains advisory; a human decides what action is appropriate.
