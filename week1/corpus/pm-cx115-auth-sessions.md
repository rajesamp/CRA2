# Auth infrastructure incident: session migration omitted live sessions

Document type: synthetic postmortem derived from a historical fixture. This is a fictional training example, not current production evidence.

Source: [canonical synthetic incidents](../../data/incidents.json), incident **CX-115**.
Service: **auth-service**. Date: **2025-10-30**. Change type: **Infra change**. Severity: **SEV1**.

## Recorded facts

The session store moved to a new cluster without copying live sessions. Most signed-in shoppers were logged out during checkout.

The fixture does not identify the storage technology, number of sessions, outage duration, or recovery procedure. It does not establish current auth health or the contents of a proposed migration plan.

## Suggested checks for a proposed change

These are review recommendations, not additional incident facts:

- Identify the state that must remain available when the session store changes.
- Ask how live sessions will be transferred or otherwise remain valid across the transition.
- Check compatibility between running application versions and both old and new storage locations.
- Review how login/session failures will be detected and what a reversal would do to sessions created during the transition.

Use CX-115 when a proposed auth or stateful-infrastructure change has a comparable continuity risk. Do not infer that any auth change must repeat this incident. Team policy and freeze applicability are separate inputs, and a stored flag is not a live calendar check. Human reviewers decide whether and when to proceed.
