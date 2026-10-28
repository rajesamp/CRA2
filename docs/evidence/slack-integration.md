# Slack integration evidence — 2026-10-18

Implementation is ready for owner installation. No Slack workspace was connected
and no live Slack message or Groq assessment was sent. The owner selected a new
app, `/cra`, and human questions in a dedicated public `#cra` channel.

## Delivered path

- `week2/slack_manifest.json`: Socket Mode, `/cra`, interactivity and
  `message.channels`, with only commands/chat:write/channels:history bot scopes.
- `week2/slack.py`: actual Bolt listeners, single-workspace/channel boundaries,
  server-held user-bound forms, immediate interaction acknowledgement, bounded
  queue, per-conversation sessions and retry deduplication.
- `week2/slack_ui.py`: catalog-derived picker, Other question form, selected
  service context and inert plain-text reply blocks.
- `week2/slack_engine.py`: existing abuse admission, graph, retrieval/MCP,
  concise answers and read-only team policy. Slack credentials join the explicit
  secret set. Session traces remain on the host, outside Slack messages.
- `week2/SLACK.md` and `slack.env.example`: manifest installation, token scopes,
  ignored local configuration, offline check and run/walkthrough instructions.

## Verification

Final Week 2 suite: **229 passed in 48.39 seconds**. This includes 33 Slack tests
using real Bolt dispatch with fake Slack API/delivery. Tests cover picker and
general forms, direct slash/channel questions, acknowledgements before agent
work, foreign channels/workspaces/shared-message rejection, forged/expired/
wrong-user contexts, mismatched services, retry deduplication, bounded queue and
expiry, session isolation, response destinations, read-only preferences, secret
withholding, private collection and per-user cooldowns. A concurrency regression
checks that a slow busy notification cannot hold the context lock and delay a
different slash command's acknowledgement.

The complete local proof at **2026-10-18T19:55:47Z** dispatched the slash menu,
service action and modal submission through actual Bolt, then ran the worker:

- Eight catalog services plus General question; selected checkout-service.
- Three actual local historical passages and both actual stdio MCP tools:
  check_system_health and get_dependency_graph, with the existing metadata gate.
- Recalled explicit high-risk preference. The offline review returned low;
  the existing policy floor produced medium, preserving the risk invariant.
- The trace recorded Groq assessment mode, `offline-slack-fixture`, zero tokens
  and `request_attempted=false`. The Slack reply contained the concise result
  and no source/tool/memory identifiers or turn badge.
- General app help stayed local, a repeated form submission did not reassess,
  and an explicit prohibited request triggered the private 15-second pause.
- Local slash dispatch acknowledgement measured 10.966 ms. This excludes Slack
  network latency and is not a live-workspace timing guarantee.

Live Slack/Groq access was forbidden by the offline proof. Its report remains
ignored in `week2/.local/slack-offline-proof.json`; synthetic private audit and
memory files remain ignored too. The private task 18 learner note was updated.

Dependency verification compared full locked package records: **all 122 existing
records unchanged**; only Slack Bolt 1.30.0 and Slack SDK 3.45.0 were added in
the Week 2 environment. Root/Week 1 dependencies and locks were not changed.
The existing web app remained on port 7862 without a restart for this feature.

## External acceptance still required

The owner must import the prepared manifest into their workspace, install the
app, create the app-level connections:write token, configure bot/app credentials
and workspace/channel IDs in ignored `.env.slack`, and invite CRA2 to the public
channel. `python -m week2.slack --check` correctly refuses absent configuration;
it never claims connectivity. Normal startup checks the bot's workspace before
opening Socket Mode. A real workspace/provider walkthrough is still pending.

This is a single-process local integration: pending jobs, retry IDs and session
traces are volatile across restart. Browser Admin traces are browser-session
specific and do not expose Slack sessions. Owner security records remain
CLI-only. No public HTTP deployment, multi-workspace OAuth distribution or
persistent Slack trace viewer was introduced.

## Subsequent owner activation

After implementation, the owner installed the prepared app and saved its values
in ignored local configuration. Bot authentication matched the configured
workspace, and the actual listener completed an authenticated Socket Mode
connection. This verifies connectivity; it does not establish live message
delivery or assessment quality. No Slack test message or new Groq request was
sent by that connection check. The earlier installation-pending status above
describes the implementation snapshot. New checkouts still require their own
private configuration and app installation.
