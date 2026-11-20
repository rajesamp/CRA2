# Version 1 acceptance

- Introduction explains CRA, recorded evidence, review checks and advisory limits.
- Google identity comes only from verified IAP claims. The UI displays a masked
  address such as ra**an@example.test, never a full address or a browser-supplied identity.
- A configured invitation list can admit additional Google identities; the default
  deployment remains owner-only. No account access grants or invitations in this slice.
- Preferences and sessions are isolated by verified identity, including requests
  that reuse another user's browser session identifier.
- Default pending owner preference: the introduction is inside IAP. Visitors see
  only themselves; the owner sees masked users active in the last five minutes
  on this instance. Activity expires and resets on restart. This does not claim
  knowledge of Google-wide login/logout status. A public intro would be separate
  from the protected application and requires the owner's visibility decision.

# Later versions

Version 2: bounded file types and size; isolated parsing; secret, instruction
injection and adversarial checks; quarantine/rejection evidence; owner-reviewed
promotion with provenance and a rebuilt, versioned retrieval index. Uploaded
content cannot authorize tools or modify the trusted corpus by itself.

Version 3: show the current approved dataset manifest with title, version, source
count and update time. A bucket illustration highlights the selected dataset title
with reduced-motion support. It reflects actual authorized metadata; loading,
empty and unavailable states are explicit. Cloud identifiers stay private.
