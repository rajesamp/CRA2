# Intent: invoke CRA2 from Slack

Date: 2026-10-18. Originator: app owner, authorized in chat.

Add a new Slack app with `/cra` and human messages in a dedicated public `#cra`
channel. Offer catalog-derived services to select, a free-text change question,
and general app questions. Specific changes use the existing Groq workflow;
app help stays local. Preserve concise answers and keep execution details out
of Slack messages. The owner selected a new-app setup rather than an existing
installation. Prepare a manifest and local credential instructions; do not
claim workspace installation or live verification without actual credentials.

All edits and local state stay inside CRA2 or `/tmp`. Preserve the existing
web app, private security records, unrelated edits and Week 1/root packages.
No live Slack message or Groq call is needed to verify implementation.
