<!-- Week 2 task 12: tool contracts; implementations belong to tasks 13–15. -->
# Week 2 tool contracts

Task 12 defines two read-only tools. The owner accepted this scope on 30 Sep
2026. Tasks 13 and 14 implement them; task 15 exposes them through MCP. These
contracts do not establish a working tool or an MCP round trip.

## Shared contract

- Accept exactly `{"service_name": "<catalog service>"}`: one nonempty string,
  at most 200 characters, with no control characters. Trim surrounding spaces;
  require an exact, case-sensitive catalog name. Reject extra arguments and
  credentials before lookup. Never infer a service from its name or history.
- Read the canonical `data/checkout_system.json` fixture on each call. Its eight
  services and ten directed edges are synthetic; external incident labels do
  not expand this catalog. Validate the source before returning facts.
- A successful result has `status: "ok"`, the resolved `service_name`, tool
  fields below, `source`, and `evidence`. `source` identifies the relative file,
  `kind: "synthetic_snapshot"`, `observed_at: null`, and `freshness: "unknown"`.
  The fixture supplies no observation timestamp. Call time recorded in a later
  MCP trace must not become observation time or imply production freshness.
- Evidence keys identify returned source fields. The agent may cite these
  snapshot facts but must label their scope. Similar historical incidents do
  not establish current health, an active incident, or shared causation.
- Tool results provide facts, never risk scores or approval/block/merge/deploy
  authority. Answers remain advisory and require a human decision. Existing
  team-policy precedence, high-risk floors, and freeze-verification safeguards
  remain active. User-facing answer/fallback copy stays configurable in
  `week1/responses.json`; tool errors expose stable codes, not raw exceptions.
- Only these two read operations are in the tool allow-list. No arbitrary paths,
  commands, URLs, credentials, production access, or Jev integration are inputs.
  Check credentials in loaded data and results before returning them; keep
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
- `freeze_window.status` is `unconfirmed` when true and `not_reported` when false.
  Neither state confirms the calendar's current applicability or absence.
- `active_incidents` is null and `active_incidents_status` is `unknown`.
  Historical records lack active/resolved status; do not convert them into
  active incidents or claim that an empty active-incident list was observed.

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

`payment-gateway` must return `Degraded`; `auth-service` must return a reported
active, unconfirmed freeze. A later explicitly observed or simulated operational
source needs its own reviewed contract; this fixture must not silently acquire
current-state claims.

## Dependency graph

```python
# Week 2 task 14 implements this task 12 contract.
get_dependency_graph(service_name: str) -> dict
```

An edge `A -> B` means A calls B. **Dependents/upstream callers** call the selected
service; **dependencies/downstream callees** are called by it. Return both
directions, each with `direct` and `transitive` sorted, unique service-name lists.
Transitive lists include direct neighbors, exclude the selected service, and
terminate even if a cycle exists. Reject unknown edge targets rather than
silently dropping them. An empty list is valid only after successful source
validation and traversal; it describes this fixture, not production completeness.

Input:

```json
{"service_name": "payment-gateway"}
```

Output example, derived from the existing fixture:

```json
{
  "status": "ok",
  "service_name": "payment-gateway",
  "dependents": {
    "direct": ["checkout-service"],
    "transitive": [
      "checkout-service", "mobile-frontend", "order-service", "web-frontend"
    ]
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
  "evidence": ["graph:payment-gateway.dependents", "graph:payment-gateway.dependencies"]
}
```

Each graph evidence key refers to traversal of the validated fixture's
`services.*.depends_on` edges in the stated direction, not an inferred relation.

## Errors and degradation

Both tools return the same error shape, without service facts or partial lists:

```json
{"status": "error", "error": {"code": "unknown_service"}}
```

| Code | Trigger | Caller behavior |
|---|---|---|
| `invalid_input` | Missing/extra arguments, wrong type, empty/oversized/control-containing name | Ask for one exact catalog service |
| `credential_rejected` | Known configured credential in input, source, or output | Stop; display the protected generic fallback |
| `unknown_service` | Well-shaped name absent from the validated catalog | Request a known service; do not widen the lookup |
| `source_unavailable` | Unreadable/missing source | State that this lookup could not be confirmed |
| `invalid_source` | Malformed/duplicate-key JSON, invalid field shapes/enums, dangling graph edges | Discard results and state the lookup failed |
| `timeout` | Later MCP transport exceeds its configured deadline | Report unavailable/unconfirmed state; no fabricated success |

Local tools need not invent timeout telemetry. Task 15 must configure a finite
MCP deadline and map actual transport failures into this contract. Never expose
raw file paths, exception bodies, SDK objects, or credentials in error output.
Any surviving historical assessment cites its actual corpus evidence and marks
operational checks unavailable; without usable evidence, provide clarification
or an unconfirmed response without a risk indication.

## Acceptance and implementation order

Task 12 is complete when this file records both signatures, field semantics,
success/error examples, provenance, and safeguards. Verify example facts against
the canonical fixture and parse every JSON example. No runtime behavior changes.

Discuss each remaining task before implementing it:

1. Task 13: known/unknown-service health checks, unconfirmed freeze semantics,
   source failures, and credential protection; record the test log.
2. Task 14: graph directions, transitive lists, cycles, isolated services, and
   unknown-service/source failures; record the test log.
3. Task 15: allow-listed MCP exposure and a real agent round trip. The parent
   `AGENTS.md` also requires Sentinel screening before tool metadata enters
   model context. Its named skill was absent from the 164 inventoried skill
   paths in three configured roots; resolve that requirement before integration.
4. Tasks 16–18: separately discuss memory schema/readback, two-session recall,
   and the expandable UI trace with recorded evidence.

Task 12 changes only this file and appended Week 2 sections in `tasks.md`,
`requirements.md`, and `docs/weekly-tracker.md`. Keep earlier acceptance and
evidence records intact; do not claim tasks 13–18 or Week 1 human acceptance.

## Verification — 30 Sep 2026

- Parsed all five JSON examples and checked health, freeze, and both graph
  directions against the canonical fixture. Both signatures have Week 2 comments.
- Preserved the complete original bytes as prefixes of all three amended
  documents and checked every relative link in the four affected documents.
- Locked offline dependency sync passed for both environments. Core tests:
  **402 passed, four live tests excluded**. Week 1 tests: **494 passed**.
- Required fast evaluation: **100/100 assessments**, minimum rubric score 10/10,
  repeatable decision context over five repeats, and zero provider attempts.
  UTC window: `2026-10-01T03:39:22.435368+00:00` to
  `2026-10-01T03:39:22.494567+00:00`. Git whitespace checks passed.

These checks verify the written examples and preserve existing behavior. They
do not demonstrate executable Week 2 tools, MCP, persistent memory, or a UI trace.

<!-- Week 2 tasks 13–14: implementation update; keep the task 12 design record above. -->
## Implemented local tools — 30 Sep 2026

Both functions now run in [`week2/tools.py`](../week2/tools.py), with shared source
validation and credential protection. Their known-service outputs and unknown-
service errors match the JSON examples above exactly. Python functions accept
missing/extra arguments only to return `invalid_input`; these arguments never
add lookup capabilities. Source reads are bounded to 1,048,576 decoded characters.
Direct and transitive graph lists both exclude self edges.

From the repository root:

```sh
uv run --locked --offline python - <<'PY'
# Week 2 tasks 13–14: call the local tools directly.
from week2.tools import check_system_health, get_dependency_graph
print(check_system_health("checkout-service"))
print(get_dependency_graph("payment-gateway"))
PY
```

[Implementation evidence](evidence/week2-tools.md) records actual calls and
verification. These tools are not yet wired into MCP or the chat; that is task 15.
