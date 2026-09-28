# ADR-002: View earlier turns in the current session

**Status:** Proposed — deferred beyond Week 1; no implementation authorized.  
**Date:** 2026-09-28  
**Deciders:** Pending; persistence policy is undecided.

## Context

The [Gradio app](../../week1/app.py) shows the active conversation with
`save_history=False`. CRA2 has no feature that restores conversations after a
refresh. The requested addition is an explicit view of earlier session turns.

## Decision

Propose a viewer for the current user and current CRA2 session.
Define “related” as earlier turns within that session; cross-session search is
outside this proposal.

The viewer is separate from persistent team-risk preferences and from text sent
to the model. It does not expand the chat adapter's existing use of recent turns
to resolve a service name.

Refresh restoration, durable storage, retention, deletion, and user/session
identity rules remain open decisions. This ADR authorizes no storage, history,
or authentication code.

## Options and trade-offs

| Option | Benefit | Cost or limitation |
|---|---|---|
| Keep the active conversation | No additional state or UI | No explicit history view |
| Add a current-session viewer — proposed | Easier review of earlier turns | Requires clear session boundaries and user isolation |
| Store conversations durably | Could restore after refresh | Requires separate storage, access, retention, and deletion decisions |

## Consequences

- Earlier exchanges become easier to inspect.
- Viewing history does not change team policy or model context.
- Week 1 remains unchanged; durable history is not approved.

## Future acceptance

- Confirm session boundaries, ownership, and any persistence policy before implementation.
- Show earlier turns in order and prevent access to another user's or session's turns.
- Verify viewing history causes no model call or team-memory write.
- Document and test refresh behavior; do not imply restoration unless approved and implemented.
