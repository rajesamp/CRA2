# Runbook: review a checkout-service config change

This is a fictional review guide derived from synthetic historical records. Its checklist is recommended review work, not a report of completed controls or live system state.

Sources: [CX-101 and CX-102](../../data/incidents.json), [synthetic catalog snapshot](../../data/checkout_system.json).

## Establish what will change

For “How risky is this change to the checkout-service config?”, first obtain the config field, current and proposed values, affected environment, and expected behavior. The question alone does not establish a specific change. Retrieve relevant history while asking for these details; do not invent a before/after state to produce a score.

## Match evidence to the mechanism

CX-101 records a payment-call timeout cut from 4 seconds to 400 milliseconds, followed by abandoned authorisations and charges without orders. CX-102 records a production retry increase from 1 to 5 while staging remained at 1, amplifying a payment-gateway slowdown into a retry storm.

These incidents are candidates for timeout, retry, and environment-drift changes. Explain the connection to the proposed field; do not cite them as proof that every checkout config change is high-risk.

## Recommended review questions

- What failure or latency behavior does the new value permit?
- Which callers and dependencies might experience that behavior?
- Can the prior configuration and consistent payment/order behavior be restored?
- Which named signals reveal retries, timeouts, or incomplete orders?

The catalog is a fictional snapshot. Week 1 retrieval does not call a current-health or freeze tool. Label such status as unverified. Cite the relevant incident or source passage for each risk reason, and leave the shipping decision to a human.
