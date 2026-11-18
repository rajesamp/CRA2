# USD 10/month demo budget

The owner supplied `10`; currency is assumed USD. This is the planning target.
No GCP budget or spend cap has been applied. The owner-only revision now uses
zero minimum and one maximum instance, 1 vCPU, 2 GiB and request-based CPU.
Actual account identifiers remain in ignored local configuration.

Live deployment discovered an inherited ingress restriction that blocks direct
external browser access. Adding an external HTTPS load balancer would add at
least USD 18.25 per 730-hour month for its USD 0.025/hour forwarding rule, before
other charges. This exceeds the total USD 10 planning target by itself. No load
balancer or budget increase has been approved. A project-level ingress exception
is a separate policy change requiring owner authorization and an authorized
administrator. Neither route has passed owner-browser acceptance.
[Forwarding-rule pricing](https://cloud.google.com/load-balancing/pricing)

Dedicated storage, Artifact Registry, KMS signing and a restricted VPC/NAT path
have been provisioned. Their charges and shared free allowances must be included
in the total; the Cloud Run subtotals below are not a complete deployment bill.

## Back-of-envelope calculation

Assumptions, not measurements: request-based billing, 1 vCPU, 2 GiB RAM, zero
minimum instances, 30 days/month, five requests per active user/day, five seconds
of billed instance time per request, serial requests without overlapping work.
Use the public Tier 1 reference rates: $0.000024/vCPU-second,
$0.0000025/GiB-second and $0.40/million requests. Verify target-region rates and
available account-wide free allowances before applying infrastructure.
[Cloud Run pricing](https://cloud.google.com/run/pricing)

`monthly requests = daily active users × 5 × 30`

`active seconds = monthly requests × 5`

`compute cost before free tier = active seconds × (0.000024 + 2 × 0.0000025)`

| Scenario | Requests/month | Billed instance hours | Cloud Run before free tier | If all free allowances remain |
|---|---:|---:|---:|---:|
| Owner testing, 10 active hours | 10,000 | 10 | $1.048 | $0 |
| 1,000 registered, 100 daily active | 15,000 | 20.83 | $2.181 | $0 |
| 1,000 daily active | 150,000 | 208.33 | $21.81 | $16.53 |
| One continuously active instance, compute only | — | 720 | $75.168 | $69.948 |

These are Cloud Run subtotals, excluding provider tokens, registry, durable
storage, network/DNS, builds, audit retention and logging beyond allowances.
The [calculated inputs and results](evidence/gcp-owner-2026-11-16/budget.json)
are retained separately. Registered users do not establish concurrency capacity.

An open streaming or heartbeat request can keep an instance active after model
work finishes. Multiple simultaneous requests can share instance time. Thus
query count alone cannot establish billed time; measure an actual browser session,
including idle tabs and reconnections. The 1,000-active-user scenario already
exceeds the total budget on its Cloud Run subtotal under these assumptions.

## Cost controls still to implement and verify

Google now lists Cloud Run as eligible for service/project spend-cap budgets.
They can block new usage once the estimated threshold is reached, but enforcement
is delayed, in-flight usage continues, and overages are billed. They do not cover
all other services. An alerts-only budget merely sends notifications.
[Spend-cap behavior and limitations](https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps)

Before configuring a cap, inspect other Cloud Run services in the target project:
a project/service cap may affect more than this demo. Prepare a concrete cap and
alert configuration with headroom for the remaining services. Owner notifications
must not include prospective invitees. The total $10 figure cannot be described
as a hard enforced ceiling.

The deployment gates also require measured stream/queue concurrency, bounded
instance count, request and token quotas, controlled runtime destinations,
retention limits, and a stop procedure. None of these can be replaced by a budget
alert or by setting a maximum instance count. No provider usage is authorized by
the offline validation results.
