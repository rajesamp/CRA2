# Task 15: LangGraph and MCP evidence

Date: 17 Oct 2026. Task 15 is implemented and verified locally. External Groq
success is not claimed. Tasks 16–18 are not implemented by this change.

## Scope and implementation

An explicit LangGraph workflow routes requests, retrieves historical evidence
when needed, calls both existing tools through the official MCP stdio client,
and returns a guarded advisory response with actual tool events. The local
server delegates to the unchanged `week2/tools.py` functions. Pure tool queries
skip retrieval and models; unsupported/clarification/boundary paths stop early.
The root and Week 1 runtime, dependency manifests/locks, and tests are unchanged.

Locked environment used: langgraph 1.2.16, mcp 1.30.0, fastembed 0.8.1, anyio 4.15.1, jsonschema 4.26.0. Python 3.13.15.
FastEmbed 0.8.1 preserves the existing index encoder fingerprint. The initial
0.9.0 resolution correctly failed with a stale-index error; no index was rebuilt
to hide the mismatch. The Week 2 environment was corrected instead.

## Real local-index and MCP round trip

Executed at `2026-10-17T20:02:27.824826+00:00`. Command:

```sh
uv run --locked --offline --project week2 python -m week2 'Change checkout-service config timeout from 4 seconds to 400 milliseconds.' --trace
```

Actual status: `evidence_only`. Orchestration: `langgraph`.
Provider used: false. Provider request attempted: false. Retrieved three chunks:

- `pm-cx101-checkout-timeout#chunk-001`
- `rb-checkout-config-risk#chunk-002`
- `rb-checkout-config-risk#chunk-001`

The client admitted the two reviewed descriptors, rechecked metadata before
calls, and recorded these actual MCP stdio results:

```json
{
  "check_system_health": {
    "status": "ok",
    "service_name": "checkout-service",
    "health": "Healthy",
    "active_incidents": null,
    "active_incidents_status": "unknown",
    "freeze_window": {
      "reported_active": false,
      "status": "not_reported"
    },
    "source": {
      "path": "data/checkout_system.json",
      "kind": "synthetic_snapshot",
      "observed_at": null,
      "freshness": "unknown"
    },
    "evidence": [
      "catalog:checkout-service.status",
      "catalog:checkout-service.freeze_window_active"
    ]
  },
  "get_dependency_graph": {
    "status": "ok",
    "service_name": "checkout-service",
    "dependents": {
      "direct": [
        "order-service"
      ],
      "transitive": [
        "mobile-frontend",
        "order-service",
        "web-frontend"
      ]
    },
    "dependencies": {
      "direct": [
        "auth-service",
        "inventory-service",
        "payment-gateway"
      ],
      "transitive": [
        "auth-service",
        "inventory-service",
        "notification-service",
        "payment-gateway"
      ]
    },
    "source": {
      "path": "data/checkout_system.json",
      "kind": "synthetic_snapshot",
      "observed_at": null,
      "freshness": "unknown"
    },
    "evidence": [
      "graph:checkout-service.dependents",
      "graph:checkout-service.dependencies"
    ]
  }
}
```

The rendered answer includes the historical passages, recorded health and graph
facts, their evidence identifiers, explicit synthetic/unknown-freshness wording,
and the advisory reminder. Local evidence mode assigns no model risk rating.

## Assessment payload and citation integration

A separate execution used the actual local index and real MCP subprocess with
an injected deterministic reviewer. This is an **offline reviewer test double**,
not a provider response. It received both tool results and returned combined
historical/tool citations. The workflow validated the combined citation set,
then preserved the existing adapter's historical-citation checks.

Executed at `2026-10-17T20:01:08.618274+00:00`. Actual status: `assessed`.
No provider request was attempted. Validated tool citations:

- `catalog:checkout-service.status`
- `graph:checkout-service.dependencies`

The test double's risk indication is not model quality evidence. The automated
integration test additionally asserts that both MCP results reach the reviewer.

## Verification results

```text
week2/.venv/bin/python -m pytest -q week2/tests
53 passed in 18.42s

.venv/bin/python -m pytest -q -m 'not live'
502 passed, 4 deselected in 4.37s

week1/.venv/bin/python -m pytest week1/tests -q
494 passed in 8.48s

.venv/bin/python scripts/run_evals.py --mode fast --repeat 5 --require-repeatable --out /tmp/cra2-week2-fast.md
100/100 assessments passed; minimum rubric 10/10; 20/20 decision contexts repeatable
0 provider attempts
```

The fast evaluation ran from `2026-10-17T20:00:19.836669+00:00` to
`2026-10-17T20:00:19.896259+00:00`. These are bounded regression/calibration
checks, not production accuracy or a Week 3/4 acceptance claim.

The 53 new checks include real subprocess round trips, known/unknown services,
unknown/changed/duplicate metadata (including changes after initial discovery),
malformed arguments, malformed wire results, result service/provenance checks,
source unavailability, real deadline cancellation and child-process cleanup,
input/output credentials, noninheritance of provider/UI secrets, model-citation
filtering, configured policy floors, and disabling environment-enabled tracing.

The first run exposed a trailing-newline argument acceptance issue and the
existing adapter's rejection of newly introduced tool citations. The newline
constraint and citation bridge were corrected; original regression tests were
not weakened. Added tests preserve both cases.

## Metadata gate and limits

The owner instructed starting task 15 after review of the file-level plan and
bounded substitute. The host accepts only the two exact reviewed descriptors;
extra names/fields, mutated descriptions/schemas and duplicates fail closed.
This replaces the unavailable Sentinel skill only for these two local tools.
It is not a semantic detector for arbitrary MCP servers, nor a cryptographic
binding between metadata and server implementation. The SDK decodes protocol
messages before application size/schema checks; those checks are not a wire-level
memory-usage guarantee. Child stderr is suppressed to avoid raw diagnostics;
failures expose protected codes rather than private exception bodies.

No persistent graph checkpoint, team memory, new UI panel, deployment, cloud IAM,
image attestation or external trace export is claimed. Tool invocation time
never establishes current production health, observed active incidents,
freshness or freeze-calendar applicability.

## External provider verification: still pending

The configured-provider attempt at `2026-10-17T20:00:21.158320+00:00` returned
`provider_unavailable`, `request_attempted=true`, and unknown token usage; both
MCP tool events remained available. This is not evidence of provider receipt or
a successful model response.

Automatic approval review rejected a network-enabled retry: it would transmit
the change query, retrieved incident passages, configured policy and MCP snapshot
results to Groq without explicit authorization for that payload/destination.
No retry was run after rejection. Completing that external check requires the
owner's explicit authorization. Do not bypass the rejection through another
network tool or indirect execution.

The remaining Week 2 work is task 16 (schema/readback), task 17 (two-session
recall), then task 18 (Gradio operational trace and screenshot).
