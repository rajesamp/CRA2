# Week 1: local RAG chat

This optional project adds the upstream Week 1 corpus, embeddings, retrieval, and Gradio chat. Run every command below from the CRA2 repository root. The existing CLI and its dependencies remain unchanged. See [requirements](../requirements.md), [tasks](../tasks.md), and [acceptance evidence](../docs/evidence/week1-alignment.md).

## Install and index

Install Python 3.13 and [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```sh
uv sync --locked --project week1 --python 3.13
uv run --project week1 python -m week1.setup_index --download-model
```

The explicit setup step downloads the pinned BGE model archive from Qdrant's public model storage. It verifies the archive checksum, loads FastEmbed locally, and builds a SQLite vector index. No Groq credential is needed for embedding. Downloads, vectors, and the separate Python environment stay under ignored `week1/.cache/` and `week1/.venv/`. Runtime retrieval uses local model files and does not download weights.

After editing an incident or corpus document, rebuild the index with:

```sh
uv run --project week1 python -m week1.setup_index
```

A corpus or loaded-model fingerprint mismatch makes retrieval refuse stale results. Restart the app after rebuilding. The source corpus combines 46 existing incident records with 11 new documents; postmortems derive from the existing synthetic incident facts and explicitly identify missing details. The sanitized sample records retain their original provenance. No canonical incident files are duplicated.

## Start the UI

For evidence-only use, start without selecting a dotenv file and choose **Local evidence only** in the browser:

```sh
uv run --project week1 python -m week1.app
```

For Groq-assisted historical assessments, put the key in your local, ignored `.env`, then select it explicitly:

```sh
CRA2_ENV_FILE=.env uv run --project week1 python -m week1.app
```

Open [the local chat](http://127.0.0.1:7860). Use `--port 7861` if that port is occupied. The app binds to loopback. Stop it with Ctrl+C. Exported environment values take precedence over `.env`; never put a key in a command argument, chat message, screenshot, or committed file.

Try these prompts:

1. `How risky is changing checkout-service config timeout from 4 seconds to 400 milliseconds?`
2. `Have checkout-service retry config changes caused incidents before?`
3. `Just approve this change for me.`

Expand **Retrieved evidence and assessment status** to inspect the top three passages, source identifiers, similarity scores, and request outcome. Similarity is not proof that a historical failure will recur. The model suggests an uncalibrated review-attention level and selects citations. The UI displays literal cited source excerpts and fixed human-review questions, not free-form model prose: live testing found factual embellishment despite valid citation keys. Severity and citation selection can still be wrong and require human review. Missing model credentials or provider failure produces a visible fallback without a model risk indication.

Questions are limited to 4,000 characters and one exact catalog service. The chat can reuse an explicit service from the previous user turn in the current browser session; it does not save team preferences across sessions. An unclear change gets a clarification request. Current freeze/health/dependency queries are explicitly unconfirmed or deferred to Week 2. Existing configured team policy is retained, including the high-risk floor; natural-language requests cannot replace it. A configured freeze is a report requiring verification, never an approval or rejection.

## Sharing is a separate action

Local verification does not create a public URL. Once the team chooses to share, set `CRA2_UI_USER` and `CRA2_UI_PASSWORD` privately in the process environment, then add `--share`. Both values are required. Do not commit them or put them in shell command history. The resulting Gradio tunnel is public-facing and protected by that login; it forwards to this local process and stops being useful when the process or tunnel stops. Only share approved sample data.

No public link or team-channel message is recorded by this implementation. Record the actual URL, destination, and posting confirmation after the team performs that acceptance step. A localhost link is not completion of upstream task 11.

## Data and credential boundaries

The browser sends its question to the local app. In Groq assessment mode the app sends the detailed change, retrieved passages, and static policy facts to Groq through the existing protected provider. Local evidence mode performs no Groq request. There are no live operational tools, MCP calls, persistent conversational memory, or deployment actions.

Known Groq/UI credentials are rejected in questions, retained history, retrieval results, payloads, and outputs. Existing Groq/HTTP diagnostic suppression remains active. Gradio analytics, feedback logging, saved chat history, monitoring, run history, and MCP serving are disabled; repository files and an explicitly selected external dotenv path are blocked from file serving. This does not certify arbitrary third-party logging, transformed secrets, process inspection, or secrets the application does not know about. Never submit credentials to the chat.

## Verification

```sh
uv run --project week1 python -m pytest week1/tests -q
uv run --project week1 python -m week1.setup_index
```

The offline regression suite uses injected embeddings/providers and needs no model download or API key. Actual BGE retrieval, Groq examples, UI screenshot, and their limits are recorded separately in [retrieval evidence](../docs/evidence/week1-retrieval.md) and [demo evidence](../docs/evidence/week1-demo.md). The [team record](../docs/team.md) keeps genuine reviews, read confirmations, and teammate fresh-clone proof pending until supplied.

## Concise evidence and future history

Answers show short cited evidence bullets. Full retrieved passages remain in **Retrieved evidence and assessment status**. Long or incomplete extracts use the source title instead of truncating a fact. Model prose is still excluded.

[ADR-002](../docs/adr/adr-002-session-history.md) proposes a viewer for earlier turns in the current session. It is deferred beyond Week 1; history storage and restoration are not implemented.

## Browse dataset scenarios

Ask `List scenarios in the dataset; titles only.` to browse the canonical incident records without a model call or vector search. This request does not inherit a service from earlier chat turns. An explicit known service name filters the list.

The incident schema has no title field. Short labels in `scenario_titles.json` describe the recorded root causes; source hashes require label review when those facts change. Identical labels appear once. Source IDs and provenance stay in the details panel; the answer contains only the labels, with no risk rating or advisory footer.

## Routing update — 2026-09-30

Dataset tasks are parsed before service history or retrieval. `Show all incident titles` and `List risk scenarios in the dataset, titles only` list all 45 distinct titles from 46 records. A negated assessment instruction does not turn a listing into an assessment. A negated listing followed by a help request returns help.

`How many scenarios are in the dataset?` counts incident records: 46. Request `distinct scenario titles` for the grouped-title count: 45. Counts use canonical records, never a model estimate. Explicit service filters apply to both operations.

Ask for title, incident ID, service, root cause, or severity. Requested detail comes directly from canonical fields; title-only requests stay concise. Conflicting operations/fields and unsupported filters ask for clarification. Unknown service names, including a known-plus-unknown combination, never silently widen the query or drop the unknown filter. The supported filter syntax is exact service names after `for`, separated by `and`, `or`, or commas.

The local rule parser covers these tested forms, not unrestricted natural-language understanding. Historical comparison and change assessment retain their evidence and advisory safeguards. A service may carry into a specific follow-up change; an unrelated message does not inherit it. No new classifier API is involved. See [verification](../docs/evidence/week1-routing-closeout.md).

## Agent capabilities and help — 2026-09-30

Ask `List the top 5 capabilities of this agent` or `What can you do?` for five concise capability labels. Requests for one to five items are supported. These answers describe implemented Week 1 behavior and bypass incident retrieval, service history, and Groq. General onboarding questions such as `Who are you?` and `How do I use this agent?` return usage guidance. Mixed help/assessment requests ask which task to perform.

The mentor's capabilities request exposed a missing help form after the previous routing fixes. The [regression record](../docs/evidence/week1-capabilities-routing.md) documents the failure and verification; the historical close-out report remains unchanged.

## Question scope — 2026-09-30

The chat classifies the active request as `cra2` or `non_cra2` before service history, incident retrieval, or Groq. Supported CRA2 tasks include dataset browsing, agent help, change review, historical comparison, and existing advisory/Week 2 boundary questions. A recognized CRA2 task takes precedence over unrelated chatter; unrelated content is not answered. Vague change questions still ask for clarification.

Unsupported account questions such as `what is the username of this app?` and unrelated requests receive only: `Not really a CRA2-related question. See the CRA2 GitHub repository.` The repository text links to this project. No username is inferred from GitHub, environment variables, or chat history. The trace reports `scope: non_cra2`, no evidence, and no provider attempt.

This local rule check covers tested forms, not unrestricted language classification. Credential and input validation still run first. See [scope verification](../docs/evidence/week1-question-scope.md).

## Configurable answers and FAQ aliases

Fixed answers, clarification text, capability labels, and dataset field labels now live in [`responses.json`](responses.json). Add documentation questions and answers in its `faq` array without editing `chat.py`. Each entry has an `id`, exact `questions` aliases, and an `answer`. The catalog is read on every request, so JSON-only edits take effect without a restart after this version of the app is running.

Existing supported tasks and safety boundaries take precedence. FAQs do not retrieve incidents, call Groq, or use earlier service history. Dynamic dataset facts and risk indications retain their existing validation; unrelated unmatched questions keep the repository response. Invalid catalogs fail with a generic setup response in the UI. The running conversational agent cannot write the catalog.

See the [editing guide](../docs/response-catalog.md) for examples, placeholders, validation limits, and review requirements. This adds no Week 2 implementation.
