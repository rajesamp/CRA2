# Plan: Slack integration

1. Confirm channel behavior and new-app setup; verify current official Slack
   Socket Mode, acknowledgement, manifest and modal contracts.
2. Add the official Bolt dependency with uv inside Week 2 only; preserve
   locked existing dependency versions and keep caches inside the workspace.
3. Implement bounded configuration, Block Kit picker/modal and adapter/session
   handlers; reuse the existing guarded workflow and concise presentation.
   Add Slack credentials to the admission guard's explicit secret set.
4. Register `/cra`, channel messages, service selection, Other question and
   modal submission in a Socket Mode runner. No live connection during tests.
5. Exercise actual Bolt dispatch offline with fake Slack delivery, real local
   retrieval/MCP and an explicit offline reviewer. Verify immediate ack,
   service/help routing, scope, retries, metadata tampering, cooldown, secrets,
   protected failures and no internal details in Slack replies.
6. Run focused and Week 2 checks; write the install/run guide, manifest,
   placeholder-only dotenv template, evidence and private learner note. Stop
   at a concrete ready-to-install integration if owner Slack credentials are
   absent. Preserve the running web app and do not send messages externally.

Result: implemented locally. Final Week 2 suite: 229 passed in 48.39 seconds,
including 33 Slack cases. Full offline Bolt-to-worker proof at 19:55:47 UTC
used actual local retrieval/MCP, recalled policy and an explicit offline Groq
reviewer. All 122 existing dependency records are preserved; only Bolt and its
SDK were added. See `docs/evidence/slack-integration.md`. The web app remains
running. External acceptance is pending: owner workspace installation, ignored
credentials and a live Slack walkthrough. No Slack message/provider call sent.
