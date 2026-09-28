# Payment dependency incident: TLS upgrade removed a required cipher

Document type: synthetic postmortem derived from a historical fixture. This is a fictional training example, not current production evidence.

Source: [canonical synthetic incidents](../../data/incidents.json), incident **CX-104**.
Service: **payment-gateway**. Date: **2025-11-20**. Change type: **Dependency upgrade**. Severity: **SEV1**.

## Recorded facts

A major TLS-library upgrade removed a cipher suite that the card processor still required. Every authorisation failed until rollback.

The fixture does not identify the library version, cipher suite, outage duration, or detailed rollback procedure. It does not establish the processor's present requirements or imply that every dependency upgrade has this risk.

## Suggested checks for a proposed change

These are review recommendations, not additional incident facts:

- Identify the library, current version, target version, and any removed protocol or cipher support.
- Confirm the external processor's current compatibility requirements from an authoritative source.
- Review a compatibility-test plan and observe authorisation failures during the proposed rollout.
- Ask whether rollback restores the required behavior and what evidence would trigger investigation.

CX-104 can support a concrete concern about compatibility with an external payment processor. Similar words such as upgrade or payment are insufficient without a relevant mechanism. The record does not define dependency topology; consult the separately labeled catalog snapshot or a future verified graph tool for that information. A human retains the shipping decision.
