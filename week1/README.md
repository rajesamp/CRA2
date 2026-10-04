# Week 1: the chat app

This project is the CRA2 app: corpus, embeddings, retrieval, and the Gradio
chat. It runs in its own environment. The shared engine under `cra2/` and the
app run side by side. Run every command below from the CRA2 repository root.
See [requirements](../requirements.md), [tasks](../tasks.md), and
[acceptance evidence](../docs/evidence/week1-alignment.md).

## Install and index

You need Python 3.13 and [uv](https://docs.astral.sh/uv/getting-started/installation/). Then:

```sh
uv sync --locked --project week1 --python 3.13
uv run --project week1 python -m week1.setup_index --download-model
```

The explicit setup step downloads the pinned BGE model archive from Qdrant's
public model storage, verifies the checksum, loads FastEmbed locally, and
builds a SQLite vector index. Embedding needs no Groq credential. Downloads,
vectors, and the separate Python environment stay under ignored `week1/.cache/`
and `week1/.venv/`. Runtime retrieval uses local model files and never
downloads weights.

After editing an incident or corpus document, rebuild:

```sh
uv run --project week1 python -m week1.setup_index
```

A corpus or model fingerprint mismatch makes retrieval refuse stale results.
Restart the app after rebuilding. The corpus combines 46 incident records with
11 new documents. Postmortems derive from existing synthetic incident facts
and mark missing details explicitly. Sanitized samples keep their original
provenance. No canonical incident file is duplicated.

## Start the UI

For evidence-only use, start without a dotenv file and pick **Local evidence
only** in the browser:

```sh
uv run --project week1 python -m week1.app
```

For Groq-assisted historical assessments, put the key in your local, ignored
`.env`, then select it explicitly:

```sh
CRA2_ENV_FILE=.env uv run --project week1 python -m week1.app
```

Open [the local chat](http://127.0.0.1:7860). Port taken? Use `--port 7861`.
The app binds to loopback; stop it with Ctrl+C. Exported environment values
take precedence over `.env`. Never put a key in a command argument, chat
message, screenshot, or committed file.

Try these prompts:

1. `How risky is changing checkout-service config timeout from 4 seconds to 400 milliseconds?`
2. `Have checkout-service retry config changes caused incidents before?`
3. `Just approve this change for me.`

Expand **Retrieved evidence and assessment status** to inspect the top three
passages, source IDs, similarity scores, and request outcome. Similarity does
not prove a historical failure will recur. The model suggests an uncalibrated
review-attention level and selects citations. The UI shows literal cited
excerpts and fixed human-review questions — not free-form model prose, because
live testing found factual embellishment despite valid citation keys. Severity
and citation selection can still be wrong; human review stays required.
Missing credentials or provider failure produces a visible fallback with no
model risk indication.

Question limits: 4,000 characters and one exact catalog service. The chat can
reuse an explicit service from the previous user turn within the current
browser session; it never saves team preferences across sessions. An unclear
change gets a clarification request. Current freeze/health/dependency queries
stay explicitly unconfirmed or defer to Week 2. Configured team policy is
retained, including the high-risk floor; natural-language requests cannot
replace it. A configured freeze is a report requiring verification, never an
approval or rejection.

## Sharing is a separate action

Local verification creates no public URL. When the team chooses to share, set
`CRA2_UI_USER` and `CRA2_UI_PASSWORD` privately in the process environment,
then add `--share`. Both values are required; do not commit them or put them
in shell history. The resulting Gradio tunnel is public-facing, protected by
that login, forwards to the local process, and stops working when the process
or tunnel stops. Share only approved sample data.

This implementation records no public link or team-channel message. Record the
actual URL, destination, and posting confirmation after the team performs that
step. A localhost link is not completion of upstream task 11.

## Data and credential boundaries

The browser sends its question to the local app. In Groq assessment mode, the
app sends the detailed change, retrieved passages, and static policy facts to
Groq through the existing protected provider. Local evidence mode makes no
Groq request. There are no live operational tools, MCP calls, persistent
conversational memory, or deployment actions.

Known Groq/UI credentials are rejected in questions, retained history,
retrieval results, payloads, and outputs. Groq/HTTP diagnostic suppression
stays active. Gradio analytics, feedback logging, saved chat history,
monitoring, run history, and MCP serving are disabled; repository files and an
explicitly selected external dotenv path are blocked from file serving. This
does not certify against third-party logging, transformed secrets, process
inspection, or secrets the app does not know. Never submit credentials to the
chat.
