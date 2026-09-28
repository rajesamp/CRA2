# Checkout config incident: retry increase amplified a payment slowdown

Document type: synthetic postmortem derived from a historical fixture. This is a fictional training example, not current production evidence.

Source: [canonical synthetic incidents](../../data/incidents.json), incident **CX-102**.
Service: **checkout-service**. Date: **2026-03-02**. Change type: **Config change**. Severity: **SEV2**.

## Recorded facts

The retry count was raised from **1 to 5 in production only**. Staging still used a retry count of **1**. During a payment-gateway slowdown, the retries produced a retry storm.

The fixture does not state the outage duration, traffic volume, exact retry timing, or recovery procedure. It does not say that every retry increase causes an outage or that payment-gateway is currently slow.

## Suggested checks for a proposed change

These are review recommendations, not additional incident facts:

- Request the current and proposed retry counts and the environments receiving the change.
- Compare staging and production settings instead of assuming their retry behavior matches.
- Examine aggregate request amplification when the payment dependency slows down.
- Ask about backoff, retry limits, rollback, and monitoring of retry traffic and payment latency; the fixture does not establish which of these controls existed.

Use CX-102 when a proposed checkout config change changes retries or creates a relevant environment mismatch. Explain that mechanism explicitly. Do not treat every config change as a recurrence. Historical evidence supports a review question; it does not authorize approval, blocking, or deployment.
