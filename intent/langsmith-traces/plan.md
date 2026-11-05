# Plan and implementation record: LangSmith traces

2026-11-04. User requested implementation. WIP: one integration, no delegation.

1. Inspect current Week 3–4 graph, telemetry, Admin callbacks, SDK and private
   configuration presence without printing credentials. Current baseline is
   `22dcfca`; preserve the unrelated dirty documentation and learning work.
2. Add `week4/langsmith_tracing.py`: explicit configuration, projection,
   bounded background batch ingestion, protected statuses/private links and
   an SDK error-callback check. Reuse installed dependencies.
3. Add real timestamps and request/turn/mode correlation in
   `week2/workflow.py` / `week2/mcp_client.py`. Keep automatic tracing disabled
   and guard LangSmith credentials before graph work.
4. Replace Admin/PIN controls in `week2/app.py` with LangSmith links/status and
   existing session metrics. Preserve server-owned history, cache badge,
   cooldown, local default, private APIs, retry/undo/clear behavior. Update only
   current help/copy/README contracts; historical evidence stays intact.
5. Verify projection and real MCP/memory/cache behavior with a controlled sink,
   actual SDK HTTP ingestion through a stub adapter, rejected-ingestion
   reporting, queue backpressure, unsafe URLs and Gradio serialization. Update
   the obsolete PIN-view tests to the owner-requested LangSmith contract.
   Disable implicit cloud export in offline UI regressions.
6. Run integration/core/Week 1 checks and existing local evaluations. Start only
   the intended localhost app, inspect the real browser and capture proof.
   Write the setup/learning handoff and bounded acceptance evidence.
7. Live activation: after the content-free check and initial review rejection,
   the owner explicitly approved memory flags, source IDs/scores, validated
   synthetic MCP facts, cache/rail outcomes, timing and correlation IDs for
   their configured LangSmith workspace. Enabled the private flag, restarted
   the intended app and verified a real local-evidence trace and private link.
   Readback: memory recalled, three sources, two MCP calls, three rail spans,
   eleven descendants. Question text and six configured sensitive values
   were excluded. No Groq request was made.
8. The owner subsequently requested a GitHub update and secret checks. Publish
   only the selected feature/security changes plus the previously completed
   Week 3–4 commits; preserve unrelated dirty docs and learning work. Use a
   fresh branch on current main because the prior Week 2 PR was squash-merged.

Actual evidence: [langsmith-traces.md](../../docs/evidence/langsmith-traces.md).
No runtime dependency installation, Groq request, Slack message or public trace
share was performed. The owner specifically asked
to open `.env`; only missing trace-enable/key fields were appended, preserving
the existing credential values and 0600 permissions. No key was displayed.
The enable flag was held false until the explicit approval, then enabled.
Final SDK regression: ingestion normalizes its input dictionaries in place;
copy the reviewed projection before ingestion so URL resolution keeps string
IDs and timestamps. A failing regression reproduced this before the fix.
