# C1 · Check retrieved evidence before CRA2 uses it

Author: Codex. Status: **for owner review**. Design date: 2026-11-22.
Input: [approved intent](intent.md) and [owner acceptance](acceptance.md), commit
`e92cece`. Scope: retrieved evidence in the protected Week 2 chat and
incident/rollback flows, including chat's Week 1 delegate.

## Requirements

| ID | Required behavior | Acceptance check |
|---|---|---|
| R1 | Equivalent formatting of the same source passage receives the same NeMo context verdict. One rejected passage withholds the entire selected batch. | Through the real local NeMo action, all three recorded must-block cases block and the benign control passes. A batch containing both kinds blocks in either order. [Stage 1 measurements](context-probes.json) |
| R2 | Ordinary incident prose, quoted historical observations, wrapped runbook text and valid non-ASCII names remain usable. A quotation that contains a full policy match is withheld, even when attributed to a source. | Fixed benign controls pass. On accepted evidence, original text, source references and citation IDs survive screening unchanged. Existing display escaping still applies. |
| R3 | Every nonempty batch is checked before it can contribute to an answer, a reviewer/provider payload, a dependent tool call, a report shown to the user or an exported trace. A cache hit receives a fresh verdict on each request. | Instrument the normal chat, legacy chat and recovery entry points. On rejection or unavailable verification, counters show zero downstream uses of the evidence. The trace and UI contain only the safe fallback and permitted metadata for that failure. |
| R4 | Missing or inconsistent verdicts, rail errors, invalid structure and oversized inputs stop protected use. A successful selection of zero records follows the existing empty-evidence behavior. | Distinguish a verified block from an unavailable check. Help with no retrieval requires no context verdict. Empty and malformed inputs never authorize an evidence-backed risk or readiness conclusion. |
| R5 | Guardrail activity stays within the current session. The panel reports the matched condition, outcome and execution state. | In two isolated sessions, only the originating session sees its event. A unique synthetic source marker is absent from blocked responses, report data, traces, telemetry/export projections and panel HTML. Safe fallbacks may still pass the output rail. |

## Design

**Screen a copy, retain the original.** In the context branch of
[LocalRails.check](../../week3/guardrails.py), apply the existing shape,
credential and [serialized size checks](../../week2/contracts.py) before
handing content to NeMo for serialization or analysis. Bound the screening
representation after transformation as well. Keep the existing NeMo action,
stage names and public verdict codes.

For each source text value, build a transient matching view using Unicode
NFKC, removal of Unicode format controls and collapse of whitespace runs to
one space. Run the existing case-insensitive context predicate on the original
and matching view. A match on either withholds the batch. Process fields
individually so unrelated values do not form a synthetic instruction. Keep
punctuation, source identifiers and citation keys intact in the actual record.
The matching view has request lifetime and never becomes evidence presented
to a reviewer. Identifiers used as references retain their existing structural
and provenance checks. Screen free-text fields that reach a consumer,
including titles as well as passage bodies.

| Consumer | Integration contract |
|---|---|
| [Graph chat](../../week2/workflow.py) | Preserve the existing order of retrieval, context check, tools and composition. Check the selected hits after retrieval or cache lookup and before giving them to downstream nodes. The retrieval cache is a source of untrusted candidates on every read. |
| [Delegated chat](../../week1/chat.py) | The Week 2 legacy node currently checks the delegate's returned trace after composition. Factor the delegate's retrieval and answer composition so Week 2 can validate the exact selected batch between them. Reuse the selection once, including on cache hits. Preserve the synchronous Week 1 caller contract and its no-retrieval short circuits. |
| [Incidents and rollback](../../week2/incident_rollback.py) | Keep bounded, local selection ahead of the check. Screen the source-derived string values selected for the report, including incident prose, catalog rollback text and displayed graph labels, in their decoded form. The current whole-report JSON string changes the representation of multiline fields. Render a successful report after verified context. Check that rendered output before releasing either the HTML or the structured report. |
| [Session activity](../../week2/guardrail_activity.py) | Reuse the closed code vocabulary and existing session limit. A verified policy match yields `block / untrusted_context`. Failed verification yields `unavailable / rail_unavailable`. A skipped check is never counted as passed. |

**Failure and compatibility.** Gate failure discards the candidate batch. Chat
keeps its static advisory failure path and recovery returns its static
blocked/unavailable report. Source selection, shape validation and safe
failure rendering may still run. Pre-rail contract or retrieval failures keep
their safe error status and cannot claim NeMo executed. Preserve source
ranking, existing tool contracts, output checks and accounting for work
actually attempted. This design requires no reindex or stored-data migration.

**Verification for build acceptance.** First commit a failing regression against
the accepted baseline. Use the existing [Week 2–4 CI job](../../.github/workflows/week2-4.yml)
on Python 3.10 and 3.13 with the pinned NeMo runtime and synthetic fixtures.
Exercise ordering through the normal host entry points with instrumented
downstream collaborators and an injected rail failure. Include cold and warm
retrieval, mixed batches, exact field/citation preservation, benign punctuation
and multilingual text, empty selection and the existing byte limit at and above
its boundary. Report missed blocks / must-block cases and false blocks /
must-allow cases separately; both numerators must be zero on the declared
fixtures. Missing results or empty denominators fail the gate. These are
fixture-level measurements. A pass establishes neither semantic faithfulness
nor general prompt-injection resistance.

**Design check, 2026-11-22.** Five existing offline tests passed on Python
3.13 at the accepted baseline: real rails on help and recovery, recovery
with an unavailable rail, closed session projection, and unavailable/skipped
status display. These runs establish the behavior to preserve. The two
recorded formatting misses still require implementation and regression evidence.

## Policy conformance

- The [repository guidance](../../CLAUDE.md) and [guardrail contract](../../docs/guardrails.md)
  require bounded inputs, advisory results, preserved provenance and safe
  errors. The matching step runs locally with the existing dependencies.
- The owner's agent-security policy requires checks before downstream actions
  and default denial on unverifiable decisions. Actual execution and the host
  outcome stay distinguishable in [session activity](../guardrail-activity-evals/spec.md).
- The protected app stays owner-only. Invitations remain on hold. C1 has no
  deployment, IAM, storage-retention or external-judge step.

## Flagged concerns

- **For owner review:** R2 deliberately withholds an exact matching instruction
  inside a quotation. A security write-up may therefore be withheld even when
  its author is describing an incident. Ordinary descriptions remain in the
  must-allow set. Accepting this spec accepts that behavior for C1.
- The accepted intent records an unresolved policy mapping for future MCP
  discovery. C1 uses the existing fixed inventory and introduces no registration
  or discovery path. Reopen the mapping with the policy owner if that scope
  changes.
- The owner selected C1 first. The source steward, peak workload/SLO, monthly
  budget and meaning of “agent substrate” remain open for their respective
  slices. C2 capacity, C3 evaluation coverage, C4 audit correlation, C5 release
  evidence and C6 product copy remain in the [backlog](findings.md).
