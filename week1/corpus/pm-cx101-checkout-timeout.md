# Checkout config incident: payment timeout cut too far

Document type: synthetic postmortem derived from a historical fixture. This is a fictional training example, not current production evidence.

Source: [canonical synthetic incidents](../../data/incidents.json), incident **CX-101**.
Service: **checkout-service**. Date: **2025-10-14**. Change type: **Config change**. Severity: **SEV1**.

## Recorded facts

The timeout for payment-gateway calls was cut from **4 seconds to 400 milliseconds**. Slow authorisations were abandoned while still in flight. Some shoppers were charged even though no order was created.

The fixture does not record the outage duration, customer count, investigation timeline, or recovery procedure. Those details are unknown. It does not establish the effect of a different timeout value or the current health of either service.

## Suggested checks for a proposed change

These are review recommendations, not additional incident facts:

- Ask for the current and proposed timeout values and the affected checkout calls.
- Check payment-authorisation latency and what happens when a request times out after the external payment operation has started.
- Examine whether cancellation, retry, and order creation can leave payment and order state inconsistent.
- Ask how to restore the prior setting and how monitoring would detect charges without completed orders.

This history is directly relevant to a checkout payment-timeout config change. A shared service or config label alone does not prove that another change has the same failure mechanism. Cite CX-101 and explain the connection before using it as a risk reason. The assessment remains advisory; a human makes the shipping decision.
