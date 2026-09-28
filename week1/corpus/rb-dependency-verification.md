# Runbook: verify payment-gateway dependencies

This fictional guide uses the committed synthetic catalog as a historical snapshot. It does not describe a live dependency lookup or authorize a change.

Source: [synthetic checkout catalog](../../data/checkout_system.json). In that file, a service's `depends_on` list names services it calls.

## Interpret graph direction explicitly

For “What services depend on payment-gateway?”, the snapshot's direct caller is **checkout-service**. Following reverse edges transitively also reaches **order-service**, **web-frontend**, and **mobile-frontend**. These are potential downstream consumers affected through the stated call chain, not four direct callers.

Payment-gateway itself lists **notification-service** as a service it calls. That outgoing dependency has the opposite direction from services that depend on payment-gateway. No relationship should be inferred merely from a service name or an incident's similar wording.

## Recommended verification work

- Specify whether the question asks for direct callers, transitive callers, or outgoing dependencies.
- Cite the catalog record and label every answer from this corpus as a snapshot.
- Confirm the current graph from an authoritative source before using it as present operational evidence.
- If current topology cannot be verified, say so instead of promoting snapshot relationships to current facts.

Week 1 does not call a dependency-graph tool. The upstream plan schedules that implementation for Week 2; this runbook is supporting corpus material only. A graph can identify review scope, but it does not establish a probability of failure or make a shipping decision.
