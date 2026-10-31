# What we built and what it proves

CRA2 Weeks 3–4 · local delivery · 2026-10-31. This is a guide to the engineering
choices and recorded evidence, not a claim of production readiness.

| Component | What it does here | Choice and implications | Recorded proof |
|---|---|---|---|
| NeMo Guardrails | Executes local input, retrieved-context and output checks | Programmable flows plus Python actions. Adds a real enforcement layer and dependency/runtime overhead. It does not grant tool permissions or guarantee factuality. | [Actual execution](evidence/week3-task-20.md) |
| LangGraph | Orders routing, memory, retrieval, tools and response composition | Keeps the workflow explicit. Guardrails constrain steps; they do not replace orchestration. | [Workflow and trace evidence](evidence/week4-task-26.md) |
| MCP | Carries the two reviewed read-only tool calls | A schema and metadata gate controls the boundary. A successful call proves returned snapshot facts, not current production health. | [Actual calls and failures](evidence/week4-task-32.md) |
| RAG | Retrieves historical passages | A citation can exist without supporting the requested mechanism. TLS history is not timeout evidence; similarity is not causation. | [Unsupported-evidence probe](evidence/week3-task-21.md) |
| Team memory | Stores explicit service preferences, not conversations | Current policy and risk floors win. Mutable policy is checked again before output; trusted team identity is fixed for the running process. | [Separate-process recall](evidence/week3-task-24.md), [mutation faults](evidence/week4-task-32.md) |
| Exact caches | Reuse query vectors, retrieval and validated tool results | Keys include scope and versions. TTL bounds retention; versions determine validity. Separate numeric changes cannot share an answer. Final-answer caching stays off. | [Correctness](evidence/week3-task-22.md), [measured speed](evidence/week3-task-23.md) |
| Observability | Correlates stages with one request ID and records bounded metadata | Counts actual invocations, not logical lookups. A failure before invocation differs from a failed tool call. No raw questions/answers/owner audit data in general persisted telemetry. | [Trace exports](evidence/week4-task-26.md) |
| Evaluations | Scores fixed local contracts and explicit fault/precision cases | Freeze cases/scorer before fixes. Keep failures and denominators. Correcting a label is different from improving the application. | [Baseline](evidence/week4-task-28.md), [analysis](evidence/week4-task-29.md), [rerun](evidence/week4-task-30.md) |
| Dashboard | Shows this browser session's actual metrics and recorded scorecards | No eligible calls means an unmeasured rate. Configured risk floors and remembered preference effects are separate. | [Browser proof](evidence/week4-task-31.md) |

## What other guardrail approaches mean

Ordinary Python and JSON-schema checks are deterministic and cheap; they cover
explicit contracts. NeMo provides programmable rail execution and flow
configuration around those checks. Model-based safety or factuality checks can
interpret more language but introduce model error, latency, costs and data
movement. These approaches can be combined. CRA2 starts with real local NeMo
actions and retained host contracts to preserve zero provider calls locally.
Existing admission screening and retrieval still use local BGE embeddings.
Zero external model requests does not mean zero local model work.
See [NVIDIA's rail types](https://docs.nvidia.com/nemo/guardrails/about-nemo-guardrails-library/rail-types)
and [registered custom actions](https://docs.nvidia.com/nemo/guardrails/latest/configure-guardrails/actions/registering-actions).

Bounded input aliases and lexical mechanism coverage are useful controls, not
general semantic understanding. A `not_disproven` coverage result is deliberately
weaker than proven support. Model risk ratings and live-model quality remain
unmeasured in this delivery.

## How to read “done”

An implemented component needs observed evidence. For example, YAML alone does
not prove NeMo ran; a badge does not prove a cache saved work; a test double is
not an actual model request; and a localhost URL is not a public deployment.
Each numbered task has an evidence file and an ignored private learner note.

The benchmark observed 906.635→167.889 ms median graph-query latency with 30
trials per condition. The unchanged main scorecard improved 16/18→18/18; the
initial reserved 2/4 and corrected-label 4/4 reports are distinct. Nine fault
demonstrations passed. These are bounded local results with their denominators,
not general accuracy, freshness or capacity guarantees.

Use the [demo script](local-demo-script.md) to connect these choices in a live
walkthrough. Hosting, backup video and prior Week 1 human acceptance remain
separate from the selected local engineering scope.
