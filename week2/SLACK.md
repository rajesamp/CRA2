# CRA2 in Slack

The local adapter is implemented. Installing a new app in your Slack workspace
and supplying its tokens are still required. No live Slack message or new live
Groq assessment was sent during development.

## What users can do

- `/cra`: choose one of the catalog's services or select **Other question**.
  Selecting a service opens a form for the change, including before/after values.
- `/cra What is this app?`: ask directly. General help runs locally.
- In the dedicated public **#cra** channel, send `CRA`, `menu` or `services` for
  the picker, or type a question directly. Reply in a thread to retain context
  for that user/thread. The bot must be invited to this channel.
- Specific change requests use **Groq assessment**, including the existing
  historical retrieval, MCP tool results, policy and risk floors. Help and
  tool-only questions do not require a model request.

Replies and pickers are ephemeral to the requesting user. Source passages,
tool dumps, memory provenance and execution traces are not posted to Slack.
The existing advisory and synthetic-evidence limitations still apply.

## Create the new Slack app

1. Open [Your Slack apps](https://api.slack.com/apps), select **Create New App →
   From a manifest**, and choose the intended workspace. Import
   [slack_manifest.json](slack_manifest.json) using the JSON tab.
2. Confirm **Socket Mode** and **Interactivity** are enabled. There is no public
   Request URL, tunnel or change to the local Gradio server.
3. Under **Basic Information → App-Level Tokens**, generate an app token with
   only **connections:write**. Keep its value locally.
4. Install the app to the workspace under **OAuth & Permissions**. The bot needs
   only **commands**, **chat:write** and **channels:history**. Copy its bot token
   locally. Workspace admin approval may be required by your Slack policy.
5. Create or choose a public **#cra** channel and invite **CRA2** to it. Keep this
   bot out of unrelated channels: Slack's history scope covers public channels
   it joins, although this adapter processes only the configured channel ID.
6. Get the workspace and channel IDs from the Slack browser URL, which contains
   `/client/<workspace-id>/<channel-id>`, or the channel's details. Store them
   only in the ignored local environment file.

Slack's official [Socket Mode guide](https://docs.slack.dev/tools/bolt-python/concepts/socket-mode/)
and [manifest reference](https://docs.slack.dev/reference/app-manifest/) describe
these setup fields. This adapter connects directly with the new app's tokens;
it does not use a Codex Slack connector.

## Configure and start locally

Run from the repository root, using the existing Week 2 environment:

```sh
cp -n week2/slack.env.example .env.slack
chmod 600 .env.slack
```

Replace the placeholders in `.env.slack` using a local editor. Include the bot
token, app token, workspace/channel IDs and the existing Groq API key. Do not
paste credentials into Slack, this chat or a tracked file. The `.env.slack`
file is ignored. Explicitly selected dotenv settings do not override exported
environment variables.

```sh
CRA2_ENV_FILE=.env.slack week2/.venv/bin/python -m week2.slack --check
CRA2_ENV_FILE=.env.slack week2/.venv/bin/python -m week2.slack
```

`--check` validates local configuration only; it does not contact Slack or Groq.
Normal startup verifies that the bot belongs to the configured workspace before
opening the Socket Mode connection. Keep the process running; stop with Ctrl+C.
Internet access to Slack and Groq is required for live operation. Existing local
retrieval artifacts must already be provisioned as documented in Week 1.

On another checkout, install from the isolated lockfile first:

```sh
uv sync --project week2 --locked
```

## First walkthrough

1. Send `/cra`. Select **checkout-service**.
2. Ask: `How risky is changing config timeout from 4 seconds to 400 milliseconds?`
3. Check the private concise risk indication and advisory reminder. An
   unavailable provider produces no model risk rating.
4. Send `/cra What is this app?`, or choose **Other question** and ask it.
5. In **#cra**, send `CRA`, choose a service and submit a question. Also try
   `What services do you support?` directly in the channel.

The adapter maps only the configured workspace to the host's existing team
policy. Slack reads preferences; it cannot change the team's high-risk flag or
freeze notes. The app owner manages these through the local app. Conversation
context is isolated by workspace, user, channel and thread.

## Boundaries and verification

Socket Mode uses Slack's authenticated connection. Interactive forms carry only
an opaque expiring context token, bound on the server to the initiating user
and workspace. Client metadata cannot choose a reply channel. Slash response
URLs are restricted to `https://hooks.slack.com/commands/…` or `/actions/…`.
Messages from other channels, bots, foreign workspaces and shared-channel
events are ignored. Channel input and modal submissions pass the existing
abuse gate before agent work; pauses are per Slack user for 15 seconds.

A bounded worker queue keeps acknowledgements ahead of retrieval/Groq work.
There are at most 16 waiting questions, 32 sessions, 128 form contexts and
2,048 retry IDs. Forms expire after 15 minutes, queued questions after two
minutes, deduplication after ten minutes, and idle sessions after one hour.
Retries are deduplicated within the process. State and pending work do not
survive a restart; an uncertain delivery is not automatically reassessed.

Each session retains up to 50 projected traces and 100 conversation messages
in the worker's memory. Browser Admin history remains specific to that browser
session; it does not display Slack traces. There is no Slack trace-read endpoint.
Out-of-scope/security records use the existing private owner audit and CLI,
not channel history or retrieval. Known Slack tokens are withheld too.

```sh
week2/.venv/bin/python -m pytest week2/tests/test_slack.py -q
```

Tests dispatch actual Bolt slash/action/modal/channel payloads with a fake
Slack client/delivery. The full local path uses actual retrieval and both MCP
tools, with an explicitly offline Groq reviewer. This verifies implementation,
not app installation, workspace permissions or live Slack delivery. A live
workspace walkthrough remains pending until the owner configures the new app.
