<!-- Week 2 tasks 13–14: actual local tool checks; MCP and UI integration are task 15 onward. -->
# Week 2 tool implementation evidence

Owner authorization: proceed with tasks 13 and 14, after the task 12 contract
was merged in PR #14. Implementation follows [the contracts](../tools.md), in
one additive [module](../../week2/tools.py), with [focused tests](../../tests/test_week2_tools.py).

## Task 13 — system health

The health tool reads and validates the canonical synthetic snapshot on every
call. It retains reported freeze uncertainty and unknown active incidents and
freshness. Inputs, source contents, and outputs pass the existing known-key guard,
including configured UI credentials. Errors expose codes without input values,
private paths, or exception bodies. No model or production lookup is involved.

Initial focused verification, before implementing task 14:

```text
uv run --locked --offline pytest -q tests/test_week2_tools.py
47 passed in 0.33s
```

Tests cover known and unknown services, invalid/missing/extra arguments, bounded
source reads, malformed/nonfinite/duplicate-key JSON, record/edge validation,
credential canaries including escaped JSON values, and reading changed health
rather than returning a cached snapshot. This is scoped offline verification,
not production health evidence or a general secret-detection claim.

## Task 14 — dependency graph

The same validated source supplies sorted direct/transitive lists in both
directions. Iterative traversal terminates on cycles, excludes self edges, and
deduplicates repeated edges. Tests verify payment-gateway and checkout-service
lists, isolated services, cycles/self edges, a 1,200-node chain, source reloads,
and the shared failure/credential boundaries for both tools.

Final local verification, after both implementations:

```text
uv run --locked --offline pytest -q -m "not live"
502 passed, 4 deselected in 4.50s

uv run --locked --offline --project week1 python -m pytest week1/tests -q
494 passed in 6.43s
```

The core count includes **100 focused Week 2 tool cases**. Both locked offline
dependency syncs passed. The required fast evaluation passed **100/100**
assessments (20 cases, five repeats), minimum rubric score 10/10, repeatable
decision context, and zero provider attempts. UTC evaluation window:
`2026-10-01T03:59:31.057654+00:00` to `2026-10-01T03:59:31.127097+00:00`.

Actual known/unknown-service outputs matched all corresponding task 12 JSON
examples exactly. Tests confirm protected generic errors and unchanged source
bytes, with model-provider access forbidden during direct tool calls. Historical
evidence and existing code/tests/configuration are preserved. The implementation
is one 165-line module and a package marker, with no new dependencies.

Repository checks preserved all **99 baseline files**, with only the three
specified documents receiving append-only updates. Relative documentation links
and Git whitespace checks passed. Exact configured-credential scanning found
**zero matches across seven changed files for two configured values**, with a
positive detection canary. The documented numeric completion limit is not an
authentication token and is excluded. Unknown/transformed credentials remain
outside that publication check; runtime canary tests cover the declared guards.

## Limits

These are actual local Python tool calls over synthetic fixture data. They do
not establish production health, active incidents, current freeze applicability,
MCP/agent integration, persistent memory, or the Gradio trace. Tasks 15–18 retain
their separate acceptance evidence. The existing advisory policy and configurable
answers in `week1/responses.json` are preserved; no Jev integration is added.

## Recorded known/unknown-service calls

Executed locally at UTC `2026-10-01T03:59:30.678693+00:00`; call time is not source observation time.


### `check_system_health` — `checkout-service`

```json
{
  "tool": "check_system_health",
  "input": {
    "service_name": "checkout-service"
  },
  "output": {
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
  }
}
```


### `check_system_health` — `unknown-service`

```json
{
  "tool": "check_system_health",
  "input": {
    "service_name": "unknown-service"
  },
  "output": {
    "status": "error",
    "error": {
      "code": "unknown_service"
    }
  }
}
```


### `get_dependency_graph` — `payment-gateway`

```json
{
  "tool": "get_dependency_graph",
  "input": {
    "service_name": "payment-gateway"
  },
  "output": {
    "status": "ok",
    "service_name": "payment-gateway",
    "dependents": {
      "direct": [
        "checkout-service"
      ],
      "transitive": [
        "checkout-service",
        "mobile-frontend",
        "order-service",
        "web-frontend"
      ]
    },
    "dependencies": {
      "direct": [
        "notification-service"
      ],
      "transitive": [
        "notification-service"
      ]
    },
    "source": {
      "path": "data/checkout_system.json",
      "kind": "synthetic_snapshot",
      "observed_at": null,
      "freshness": "unknown"
    },
    "evidence": [
      "graph:payment-gateway.dependents",
      "graph:payment-gateway.dependencies"
    ]
  }
}
```


### `get_dependency_graph` — `unknown-service`

```json
{
  "tool": "get_dependency_graph",
  "input": {
    "service_name": "unknown-service"
  },
  "output": {
    "status": "error",
    "error": {
      "code": "unknown_service"
    }
  }
}
```
