# Runbook: compare a proposed change with historical incidents

This fictional review guide explains how to use synthetic history and separately labeled sanitized samples. It does not establish current health or a new operational event.

Sources: [synthetic incidents](../../data/incidents.json), [sanitized samples](../../data/sample_incidents.json), [provenance guide](../../data/README.md).

## Resolve the reference before claiming a match

For “Have we had incidents from similar changes before?”, ask which service, change category, and concrete modification the user means if they are missing from the current conversation. Retrieve specific passages and retain their incident IDs and service names.

## Judge relevance, not just word overlap

- Compare the proposed failure mechanism with the recorded root cause.
- Distinguish same-service history from an analogy involving another service.
- Preserve the original service, incident ID, date, severity, and change-type label.
- Do not claim that an external sample happened to the catalog service.
- Do not say that a deployment caused an incident labeled “No change” without supporting evidence.

For example, CX-101 concerns a checkout payment timeout, while CX-104 concerns a payment-gateway TLS-library compatibility failure. The word payment alone does not make both appropriate evidence for every change.

## Report limits visibly

If no retrieved passage supports the proposed mechanism, say that the corpus does not establish a matching incident. A low similarity score or an absent match is not proof of safety. Suggested checks must be labeled as recommendations rather than invented incident facts. The final answer should cite the selected source passages and state that a human makes the shipping decision.
