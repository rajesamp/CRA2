# ADR-002: View earlier turns in the current session

- **Status:** Proposed. Deferred. No implementation authorized.
- **Date:** 2026-09-28
- **Deciders:** Pending. Persistence policy is undecided.

## Context

The [Gradio app](../../week1/app.py) shows the active conversation with
`save_history=False`. Nothing restores a conversation after a refresh. The
requested addition is an explicit view of earlier session turns.

## Decision

Propose a viewer scoped to the current user and current CRA2 session.
"Related" means earlier turns in that session. Cross-session search is out of
scope.

The viewer is separate from persistent team-risk preferences and from text sent
to the model. It does not change the chat adapter's existing use of recent turns
to resolve a service name.

Refresh restoration, durable storage, retention, deletion, and user/session
identity rules stay open. This ADR authorizes no storage, history, or
authentication code.

## Options

| Option | Benefit | Cost or limitation |
|---|---|---|
| Keep the active conversation | No extra state or UI | No explicit history view |
| Add a current-session viewer (proposed) | Easier review of earlier turns | Needs clear session boundaries and user isolation |
| Store conversations durably | Could restore after refresh | Needs separate storage, access, retention, and deletion decisions |

## Consequences

- Earlier exchanges become easier to inspect.
- Viewing history changes neither team policy nor model context.
- Durable history is not approved.

## Future acceptance

- Confirm session boundaries, ownership, and any persistence policy first.
- Show earlier turns in order; block access to another user's or session's
  turns.
- Verify that viewing history triggers no model call and no team-memory write.
- Document and test refresh behavior. Do not imply restoration unless it is
  approved and implemented.