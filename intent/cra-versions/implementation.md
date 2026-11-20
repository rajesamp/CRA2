# Version 1 boundary

The public introduction runs as a separate Cloud Run service using the
`week2.landing` entrypoint. It serves static explanation, CSS and a fixed sign-in
redirect. It does not mount Gradio or import identity, storage or workflow code.
Only the exact HTTPS app URL comes from runtime configuration; request parameters
cannot choose the redirect. Its dedicated runtime identity receives no role
grants. The existing app keeps IAP and owner-only authorization. The welcome tab
also remains available after login. Versions 2 and 3 remain marked as planned.
No upload or dataset mutation is enabled.

`Principal` contains the verified subject hash, a masked email and the owner flag.
The display callback requires the server's verified request state and matching
Gradio username. Full account emails do not enter Gradio state or display output.
Recent activity is bounded, process-local and expires after five minutes. Every
signed-in visitor can see all masked recent users, as explicitly requested.
The public introduction never includes the list. Refresh updates the view;
there is no background presence heartbeat and no persistent login directory.

Cloud access defaults to the single `CRA2_OWNER_EMAIL`. The optional, private
`CRA2_ALLOWED_EMAILS` comma-separated list prepares exact additional identities;
it does not grant IAP permission or send invitations. Both IAP authorization and
the application list must admit an account. No additional identities are being
configured in the deployment for this release.

The Gradio browser protocol now hashes each browser session reference with the
verified principal key. This covers direct UI callbacks, queue submission,
queue reads and heartbeat cleanup. Cancellation additionally requires ownership
of the queued event and matching namespaced session. Unsupported APIs, uploads,
deep links, component-server calls and event streams are denied. Private responses
are not cached. Review this boundary on every Gradio upgrade.

Preferences retain their existing per-principal Cloud Storage keys. Chat state,
queues, cooldowns and recent activity remain in process memory; this release does
not establish multiple-instance operation or capacity for 1,000 active users.

Tests include real ES256 identity validation, an uninvited-user negative control,
actual mounted Gradio state writes/reads with the same and stolen session IDs,
event cancellation ownership, owner/member presence visibility, HTML escaping,
expiry/capacity, and separate durable preferences for two identities.

The public route inventory is limited to `/`, `/styles.css`, `/signin` and
`/healthz`. Tests cover anonymous rendering, fixed redirect, absent private routes,
invalid redirect configuration and security response headers. Container checks
exercise both entrypoints with networking disabled. The public service uses zero
minimum and one maximum instance, the existing restricted VPC egress, no bucket
or owner-identity environment variables, and no provider credentials. A public
service still has traffic-dependent costs; no hard monthly cost guarantee is made.
