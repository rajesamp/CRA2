<!-- Week 2 task 12: tool contracts; implementations belong to tasks 13–15. -->
# Week 2 tool contracts

Task 12 defines two read-only tools. The owner accepted this scope on
30 Sep 2026. Tasks 13 and 14 implement them; task 15 exposes them through MCP.
A contract alone does not establish a working tool or MCP round trip.

## Shared contract

All inputs:

- Exactly `{"service_name": "<catalog service>"}` — one nonempty string, at
  most 200 characters, no control characters.
- Trim surrounding spaces, then require an exact, case-sensitive catalog name.
- Reject extra arguments and credentials before lookup. Never infer a service
  from its name or history.

Source handling:

- Read the canonical `data/checkout_system.json` fixture on every call.
  Its eight services and ten directed edges are synthetic; external incident
  labels never expand this catalog.
- Validate the source before returning facts.

Success results:

- `status: "ok"`, the resolved `service_name`, tool fields, `source`, and
  `evidence`.
- `source` carries the relative file path, `kind: "synthetic_snapshot"`,
  `observed_at: null`, and `freshness: "unknown"`. The fixture has no
  observation timestamp. Call time in a later MCP trace must not become
  observation time or imply production freshness.

Evidence and boundaries:

- Evidence keys identify returned source fields. The agent may cite these
  snapshot facts but must label their scope. Similar historical incidents
  never establish current health, an active incident, or shared causation.
- Tool results provide facts, never risk scores or approval authority.
  Answers stay advisory and need a human decision. Team-policy precedence,
  high-risk floors, and freeze-verification safeguards stay active.
  User-facing answer copy stays configurable in `week1/responses.json`; tool
  errors expose stable codes, never raw exceptions.

Tool allow-list:

- Only these two read operations. No arbitrary paths, commands, URLs,
  credentials, production access, or Jev integration.
- Check credentials in loaded data and results before returning them; keep
  secrets out of prompts, errors, evidence, logs, and future UI traces.

## System health

```python
# Week 2 task 13 implements this task 12 contract.
check_system_health(service_name: str) -> dict
```

Return `health` from the service's recorded `status`, accepting only `Healthy`
or `Degraded` for this fixture. Return the recorded freeze boolean separately
from its verification state:

- `freeze_window.reported_active` is the exact fixture boolean.
- `freeze_window.status` is `unconfirmed` when true and `not_reported` when
  false. Neither state confirms calendar applicability or absence.
- `active_incidents` is null and `active_incidents_status` is `unknown`.
  Historical records lack active/resolved status. Do not convert them into
  active incidents or claim an empty active-incident list was observed.

Input:

```json
{"service_name": "checkout-service"}
```

Output example, derived from the existing fixture:

```json
{
  "status": "ok",
  "service_name": "checkout-service",
  "health": "Healthy",
  "active_incidents": null,
  "active_incidents_status": "unknown",
  "freeze_window": {"reported_active": false, "status": "not_reported"},
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
```

## Dependency graph

```python
# Week 2 task 14 implements this task 12 contract.
get_dependency_graph(service_name: str) -> dict
```

Return both directions of the recorded graph for the named service:

- `dependents` lists services that depend on the named service (`direct` and
  `transitive`).
- `dependencies` lists services the named service depends on (`direct` and
  `transitive`).
- Lists are sorted, deduplicated, and cycle-safe. Self-edges are excluded
  from both lists.
- Edges come only from the fixture. Never infer an edge from history,
  incidents, or similarity.

Direction is defined by A → B: A depends on B. Then A's dependents call A,
and A's dependencies are the services A calls.

Input:

```json
{"service_name": "payment-gateway"}
```

Output example from the existing fixture:

```json
{
  "status": "ok",
  "service_name": "payment-gateway",
  "dependents": {
    "direct": ["checkout-service"],
    "transitive": ["checkout-service", "mobile-frontend", "order-service", "web-frontend"]
  },
  "dependencies": {
    "direct": ["notification-service"],
    "transitive": ["notification-service"]
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
```

## Error contract

Both tools return `{"status": "error", "error": {"code": "<code>"}}`. Codes
are stable strings, never exception bodies or input values:

| Code | Cause |
|---|---|
| `invalid_input` | Malformed name, extra arguments, or unexpected fields |
| `unknown_service` | Name not in the catalog after trimming |
| `invalid_source` | Fixture missing content, malformed, too large, or invalid records |
| `source_unavailable` | Fixture not readable |
| `credential_rejected` | A known credential appeared in inputs, source, or output |

Steel-thread examples:

- `check_system_health("auth-service")` →
  `health: "Healthy"`, `freeze_window.status: "unconfirmed"`.
- `check_system_health("")` → `invalid_input`.
- `get_dependency_graph("auth-service")` →
  direct dependents sorted: `["mobile-frontend", "order-service", "web-frontend"]`.
- `get_dependency_graph("not-a-service")` → `unknown_service`.
