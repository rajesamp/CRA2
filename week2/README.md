# Week 2 task 15: LangGraph and local MCP

Run from the CRA2 repository root. This is the task 15 engineering entry point;
the existing Gradio app stays unchanged until task 18.

```sh
uv sync --locked --project week2 --python 3.13
uv run --locked --project week2 python -m week2 'What services depend on payment-gateway?' --trace
uv run --locked --project week2 python -m week2 'Is checkout-service current health okay?' --trace
```

These queries cross a real stdio MCP boundary and need no retrieval model or
provider. The graph uses the reviewed two-tool inventory; it does not expose
arbitrary servers or commands.

## Full assessment path

The existing Week 1 local model/index can be reused: FastEmbed is pinned to
0.8.1 to preserve that encoder identity. If this is a fresh clone, provision
the checksum-pinned model and build the local index explicitly:

```sh
uv run --locked --project week2 python -m week1.setup_index --download-model
```

Then run without a provider:

```sh
uv run --locked --project week2 python -m week2 'Change checkout-service config timeout from 4 seconds to 400 milliseconds.' --trace
```

The default is **Local evidence only**: three retrieved passages, both MCP
tools, and no model risk indication. Pure tool queries skip retrieval entirely.
Ask for one exact service. An unspecified freeze question requests a service
rather than inferring one.

`--mode 'Groq assessment'` opts into the existing protected Groq provider
adapter. It sends the change, retrieved passages, configured policy and MCP
results to Groq. A configured key alone is not permission for the agent to send
that payload: the implementation session's network-enabled validation remains
pending explicit owner authorization. Provider failures preserve tool evidence
and produce no model risk indication. Never put credentials in arguments or
chat text; use the existing explicitly selected ignored dotenv configuration.

## Execution and trust boundaries

```mermaid
flowchart LR
    A[Validated question] --> B[Deterministic routing]
    B -->|assessment| C[Historical retrieval]
    C --> D[MCP client and metadata gate]
    B -->|tool question| D
    D --> E[Local MCP server]
    E --> F[Existing health and graph functions]
    F --> G[Validated results]
    G --> H[Compose or assess with evidence]
    H --> I[Guarded answer and sanitized trace]
    B -->|help or boundary| I
```

- `workflow.py`: explicit `StateGraph`, bounded routes and ephemeral state.
  Existing Week 1 modules own retrieval, policy and historical assessments.
- `contracts.py`: exact reviewed names/descriptions/schemas, argument/result
  validation, provenance and service checks. This bounded gate substitutes for
  the unavailable Sentinel skill; it is not a general tool-poisoning detector.
- `mcp_client.py`: discovery, revalidation before each call, at most two unique
  calls, a 12-second default deadline, and subprocess cleanup. Partial outputs
  are discarded after a transport/metadata failure.
- `mcp_server.py`: exactly two read-only tools. No provider or UI credentials
  are passed to the child. Stdout carries protocol messages only.
- `responses.json`: configurable Week 2 presentation copy, complementing the
  unchanged Week 1 response catalog.

Every successful result is labeled **synthetic snapshot**. Observation time,
freshness and active incidents stay unknown; freeze applicability stays
unconfirmed. An actual call does not establish current production state.
Unknown service/source and protocol failures remain protected errors.

The workflow passes tool facts and evidence identifiers into the reviewer.
Combined citations are checked at the Week 2 boundary; the existing adapter
continues checking historical citations and policy floors. The UI-facing
answer renders validated tool facts separately with their evidence identifiers.
Model prose is not exposed as independent operational truth.

LangSmith tracing is explicitly disabled for this workflow, including when the
environment enables it. Raw graph state is not the exported trace. No persistent
checkpointer, conversation store, preference writes, or external telemetry is
introduced. Tasks 16–18 remain separate work.

## Verify

```sh
uv run --locked --offline --project week2 python -m pytest week2/tests -q
```

Tests exercise actual MCP subprocesses, metadata mutation between discovery and
invocation, malformed results, known/unknown services, unavailable sources,
deadline cleanup, input/output credentials, both tools reaching the assessment
payload, and unchanged policy/advisory behavior. Provider/retrieval doubles in
offline tests are labeled separately from actual protocol and local-index runs.

[Task 15 evidence](../docs/evidence/week2-task-15.md).
