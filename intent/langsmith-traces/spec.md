# Specification: LangSmith trace showcase

Keep automatic framework tracing disabled, including graph/rail initialization.
Instrument actual graph nodes, reviewer invocation, MCP calls and NeMo checks
with UTC start/end timestamps. After the guarded result is complete, project
only allow-listed execution facts into root/child LangSmith runs.

Root names contain turn and original review mode. Every run has the same
conversation `thread_id` and request identity. Memory spans carry recall status
and effective boolean flags, never raw records/notes/team identity. Retrieval
spans carry at most three source IDs/scores. MCP tool spans contain validated
catalog inputs and synthetic outputs. Cache reuse is represented in stage
outputs, not as a fabricated MCP invocation. Observed provider usage is attached
only where available; offline reviewer spans are not labeled model calls.

Exclude question/answer text, conversation history, prompts, passages, private
policy notes, owner records, SDK objects and environment values. Check known
Groq/LangSmith credentials at the relevant input/export boundaries. Disable
credential-bearing SDK diagnostics and omit runtime-environment metadata.

Export requires `CRA2_LANGSMITH_ENABLED=true` and a local API key. Support US/EU
SaaS endpoints, classic projects, and the installed SDK's agent/environment
addressing. Reject conflicting destinations and unreviewed endpoints. Never
manufacture a public trace URL. Deep links are resolved using the SDK and
checked against the official UI hosts and known credentials before display.

One daemon worker, queue capacity 16, status capacity 512, at most 48 projected
runs / 64 KiB per tree. Use completed batch ingestion without raw callbacks.
The SDK may swallow ingestion failures, so its error callback must be clear
before recording submission success. URL lookup is separate: a tracing-only
key may ingest successfully without read permission. Upload errors, queue
saturation and status eviction are visible but do not change the answer.

The LangSmith browser tab has a 50-turn selector, protected upload status,
private link, refresh/polling and collapsed session-only metrics. No PIN or
raw JSON viewer. Retry retains an additional cloud run for the same turn;
undo affects a local link only; clear starts a fresh conversation/thread.
Cloud retention stays under the user's LangSmith account. No old audit or
conversation data is backfilled. Existing local telemetry remains intact.

Setup is in [week2/LANGSMITH.md](../../week2/LANGSMITH.md). Sources:
[instrumentation](https://docs.langchain.com/langsmith/annotate-code),
[privacy](https://docs.langchain.com/langsmith/mask-inputs-outputs),
[threads](https://docs.langchain.com/langsmith/threads), and
[account/key setup](https://docs.langchain.com/langsmith/create-account-api-key).
Verified against the installed LangSmith 0.14.11 SDK; no dependency change.
