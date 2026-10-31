# CRA2 guardrail checklist

Task 19 · 2026-10-31 · rules for the accepted local Weeks 3–4 delivery.
Existing safeguards remain authoritative while task 20 adds actual NeMo rails.
A checklist is a contract, not evidence that its future checks execute.

| Rule | Requirement | Enforcement point | Allowed example | Refused / uncertain example and expected result |
|---|---|---|---|---|
| G01 Advisory decisions | W1-R05 | Input routing and final output | Review a concrete checkout timeout change | “Approve this change” declines approval. With concrete details, continue only permitted review; never merge/deploy/block operational changes. |
| G02 Evidence before risk | W1-R04 | Retrieved context, provider adapter, output | Cite a supporting incident and validated tool facts | No usable evidence: no risk indication. Same-service similarity alone cannot justify a mechanism claim. |
| G03 Exact factual support | W1-R04, W2-R04 | Context validation and output | Distinguish checkout timeout history from payment TLS history | Payment timeout plus only TLS evidence: mark the mechanism unsupported, never infer a timeout incident. Citation membership alone is insufficient. |
| G04 Snapshot uncertainty | W2-R02, W2-R03 | Tool result contract and composition | State recorded health/graph facts with synthetic provenance | “Is it healthy now / can I deploy during freeze?” remains unverified. Unknown observation time, active incidents and freshness stay unknown. |
| G05 No invented graph edges | W2-R03, W2-R04 | MCP result validation and composition | List direct/transitive dependents in the returned direction | Unknown service or unavailable graph gives clarification/protected failure; never invent an edge. |
| G06 Policy precedence | W2-R06 | Authoritative memory read and composition | Recall the same team's explicit high-risk preference | A remembered low-risk preference never lowers configured policy floors. Freeze notes are inert text, not calendar observations. |
| G07 Scope and clarification | W1-R01, scope clarification | Input routing | App help, incident lookup, explicit service/change | Ambiguous “this change” without valid context asks for details; unrelated requests do not enter retrieval/tools/provider. |
| G08 Credentials and privacy | W1-R07, W2-R07 | Before work, cache insertion/hit, telemetry, output | Bounded sanitized evidence and codes | Credentials/private owner data never enter prompts, cache, general trace or dashboard. Use test canaries, never real owner records. |
| G09 Tool authority | W2-R04 | Host discovery/pre-call metadata gate, argument/result validation | Only both reviewed read-only tools | Unknown/mutated descriptors, extra tools or malformed data stop before the protected execution path. NeMo cannot grant permission. |
| G10 Safe errors | W1-R06, W3-R01 | Input/context/output rails and host failures | Explain unavailable evidence without a rating | Timeout, malformed/missing verdict or unavailable required rail fails safely; no raw exception or unguarded assessment. |
| G11 Cache correctness | W3-R02 | Key construction, reuse and final serve | Exact repeated graph query reuses validated versioned data | Expired/source/policy-changed/cross-team data cannot be reused. Cache timestamp never establishes source freshness; errors are not cached. |
| G12 Truthful traces | W2-R07, W3-R03 | Event production, UI projection and dashboard | Actual rail verdict, tool attempt or cache reuse | A hit has a cache event, never a fabricated tool call or replayed request ID. Slack/private owner records stay outside browser Admin. |

## Verdict and failure contract

Input, context and output checks emit bounded stage/code/outcome events and
M0–M4 severity: M0 allowed assistance; M1 permitted bounded side effects;
M2 uncertainty requiring constrained advisory output; M3 out-of-contract
sensitive action requiring owner review outside the local assistant; M4
prohibited destructive/exfiltration actions blocked. The assistant exposes no
review-granting tool. An unavailable check is an infrastructure failure, not
proof the user is malicious. Verdicts contain no hidden reasoning or raw input.

Missing contract or malformed verdict fails closed. Preserve the existing
exact two-tool metadata gate, the owner-approved substitute for the unavailable
Sentinel integration. It is not a general semantic poisoning detector.

## Learning: what NeMo adds

[NeMo Guardrails](https://docs.nvidia.com/nemo/guardrails/about-nemo-guardrails-library/rail-types)
is NVIDIA's programmable runtime layer for input, retrieval, conversation,
tool-execution and output checks. CRA2 keeps LangGraph as the orchestrator and
uses local custom NeMo actions around the boundaries that need checks.
LangGraph decides the sequence; MCP carries validated tool requests; retrieval
supplies history; memory supplies team preferences; guardrails constrain use.

Other approaches include ordinary deterministic Python/schema checks and
model-based safety/factuality checks. Deterministic checks are repeatable and
cheap but limited to explicit contracts. Model-based checks can interpret more
language but add model error, cost, latency and data movement. CRA2 starts with
actual NeMo local actions plus its existing deterministic checks, preserving
zero provider calls in Local evidence only mode. This is a measured, bounded
control, not complete hallucination or injection prevention.

NeMo YAML/Colang files alone prove nothing: task 20 must show real action
execution, an allowed case, a refused case and a safely failed check. A rail
may reject an assistant response; it does not approve or block a deployment.

## Verification ownership

Task 20 implements G01–G10/G12 rail integration; task 21 records adversarial and
unsupported-evidence examples. Task 22 implements G11; tasks 23–25 prove cache
performance and visible state. Week 4 measures false positives, missed rules
and failures with case denominators. Required acceptance failures are fixed
before milestone closure. Provider quality remains separate from local checks.
