# CRA2 trace showcase in LangSmith

The LangSmith tab replaces the Admin PIN/trace panel. It shows a selected
turn's private LangSmith link and upload status. Session metrics remain in a
collapsed accordion. Local evidence only stays the default.

## 1. Create the account and key

1. Sign in at [LangSmith](https://smith.langchain.com).
2. Open **Settings → API Keys → Create API Key**. For a personal local demo,
   a personal access token supports ingestion and resolving private trace links.
   A workspace-scoped tracing-only key can submit traces but may not resolve
   individual links; use the signed-in LangSmith UI to find those runs.
3. Copy the key once into CRA2's existing private `.env`; never paste it into
   chat, a tracked file, a screenshot, or a command argument.

[Official account/key guide](https://docs.langchain.com/langsmith/create-account-api-key).
The SDK is already installed in CRA2's locked Week 2 environment; no global
installation is needed.

## 2. Choose the destination shown by your workspace

Use exactly one of these layouts. Don't combine agent addressing and a project.

If your workspace has **Agents**, create an **Observability** agent in the UI,
copy its Agent ID, and add to private `.env`:

```dotenv
CRA2_LANGSMITH_ENABLED=true
LANGSMITH_API_KEY=<your-private-key>
LANGSMITH_AGENT_ID=<the-agent-id-from-your-workspace>
LANGSMITH_AGENT_ENVIRONMENT=local
LANGSMITH_TRACING=false
```

Remove `LANGSMITH_PROJECT`, `LANGCHAIN_PROJECT` and `LANGCHAIN_SESSION` from
the selected configuration/exported environment when using agent addressing.
Register the agent once; a tracing-only key cannot create that agent.

If your workspace has **Tracing Projects**, use:

```dotenv
CRA2_LANGSMITH_ENABLED=true
LANGSMITH_API_KEY=<your-private-key>
LANGSMITH_PROJECT=CRA2
LANGSMITH_TRACING=false
```

Omit both agent variables in the project layout. The default supported region
is US. For an EU account, also set:

```dotenv
LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
```

This integration currently allows only the official US and EU SaaS endpoints.
If a key is scoped to multiple workspaces, also set `LANGSMITH_WORKSPACE_ID`
to the ID from your workspace's Settings → General. Keep that ID local too.
Exported environment values take precedence over the selected dotenv file.

[Official tracing setup](https://docs.langchain.com/langsmith/observability-quickstart).

## 3. Launch with the private configuration

From the repository root, restart the owned CRA2 app using:

```sh
CRA2_ENV_FILE=.env week2/.venv/bin/python -m week2.app --port 7862
```

Open `http://127.0.0.1:7862/`. Loading dotenv remains explicit. Don't start a
second copy on the same occupied port. Saving `.env` requires an app restart;
the browser does not receive credentials or change the host configuration.

## 4. Showcase a trace

In Local evidence only, send these in order:

1. `Remember that checkout-service is always high-risk for our team.`
2. `How risky is changing checkout-service timeout from 4 seconds to 400 milliseconds?`
3. Repeat question 2 to inspect cache reuse.

Open the LangSmith tab and choose a turn. Its status changes from queued to
submitted after the background uploader finishes. Follow **Open this trace in
LangSmith** and sign in to the configured workspace. If your key cannot resolve
links, open LangSmith and find the CRA2 project or configured agent/environment.
Runs are named with turn and mode, and grouped by the conversation thread ID.

The tree shows actual graph stages, memory recall/effective flags, retrieved
source IDs and scores, actual MCP results, cache use, NeMo checks, and provider
attempt status. Cache hits appear as reuse in the tools/retrieval output;
they do not create fabricated MCP calls. Groq mode adds a model span only when
the provider adapter actually runs, with observed usage when available.

## Export boundary and failure behavior

- Browser requests only. Slack, CLI and evaluation traces stay on their existing
  local paths; they are not silently uploaded or added to the browser dashboard.
- Raw question/answer text, chat history, prompts, retrieved passages, saved
  freeze notes, team identity, owner security records and raw SDK objects are
  excluded. Tool outputs are validated synthetic snapshot facts, not current
  production claims. Internal reasoning is never exported.
- Automatic LangGraph/NeMo tracing remains disabled, even if a global environment
  variable enables it. Explicit manual SDK ingestion sends only the reviewed
  projection; `CRA2_LANGSMITH_ENABLED=true` is the separate opt-in.
- The uploader has one worker, a 16-request queue, at most 48 spans / 64 KiB per
  projected tree, and bounded SDK request timeouts. Queue saturation skips
  export; upload or link-resolution failures do not change the assessment.
- The integration observes the SDK's ingestion error callback, because batch
  ingestion may report a failure without raising it. **Submitted** means the
  SDK ingestion completed without a reported error, not that a reviewer has
  opened the trace. URL lookup is separate and may be unavailable with a
  tracing-only key. No public trace share link is created.
- Retry creates another uploaded run for the same turn. Undo removes a local
  turn link only. Clear starts a new conversation/thread. Uploaded traces are
  retained according to your LangSmith settings; clearing CRA2 does not delete
  them. The latest 50 local turn links are held server-side until clear/refresh.
- Saving a key enables external trace transmission when the explicit flag is
  true. Local evidence only still makes no Groq request, but these selected
  execution facts will be sent to LangSmith. Set the flag false and restart
  to disable exports. Existing private audit records are never backfilled.

[SDK instrumentation](https://docs.langchain.com/langsmith/annotate-code) ·
[Sensitive-data controls](https://docs.langchain.com/langsmith/mask-inputs-outputs) ·
[Thread grouping](https://docs.langchain.com/langsmith/threads).
