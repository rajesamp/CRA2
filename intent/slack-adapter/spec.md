# Spec: Slack Socket Mode adapter

Use Slack's official Bolt SDK in the isolated Week 2 environment. Socket Mode
avoids publishing the local Gradio app or introducing an HTTP endpoint. Supply
a new-app manifest with `/cra`, interactive controls, `message.channels`, and
only `commands`, `chat:write`, `channels:history` bot scopes. The app token needs
`connections:write`. Keep workspace/channel IDs and bot/app credentials in an
explicitly selected ignored dotenv file. Fail closed when configuration is
missing; never print secrets or SDK payloads.

`/cra` opens a private service picker and an Other question button. Selecting a
service opens a modal with that service and a required question. Other question
opens the same form with General question selected. `/cra <question>` and human
messages in the configured channel accept direct questions. Ignore other
channels, bot/subtype events, foreign workspaces and Slack Connect messages.

Acknowledge interactions before model/retrieval work. Use a bounded background
queue, deduplicate retries, serialize each conversation, and scope session
history by workspace/user/channel/thread. Bind modal context to the requesting
user and workspace using server-held expiring random tokens. Never trust
destinations supplied by view metadata. Channel answers are ephemeral to their
requesting user; slash replies use Slack's response URL restricted to Slack.

Reuse the existing graph, abuse admission/cooldown, private owner audit,
concise presentation and persistent team policy. Map only the configured
workspace to the host's existing team policy and expose it read-only; this request
does not authorize every Slack user to modify team policy. Keep token-bearing
input out of the graph, model, logs and stored history. Retain only bounded
session traces in memory; no trace browser endpoint or owner-audit viewer.

Non-goals: OAuth distribution, public deployment, arbitrary channel discovery,
workspace administration, private-channel support, authenticated web admin,
or a live provider/workspace test before configuration by the owner.
