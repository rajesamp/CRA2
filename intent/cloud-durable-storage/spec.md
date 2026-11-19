# Storage contract

- Bind preferences to the verified IAP subject, configured team, and catalog
  service. Merge concurrent changes with generation preconditions. Preserve
  preferences until updated. Record a write attempt before any mutation.
- Cloud audit is append-only metadata. Its bucket retains events for 30 days
  and lifecycle deletion removes eligible events. The runtime can create audit
  objects and inspect bucket policy. It has no audit object read or delete grant.
- Keep compact request telemetry for seven days with prefix-scoped lifecycle
  deletion. Expiring telemetry does not delete preferences or impose a lifetime
  row limit. The periods are proposed defaults for owner acceptance.
- Fail closed on missing configuration, wrong storage policy, and required
  storage errors. Use the attached service identity. Preserve local SQLite and
  its existing behavior.
- Rehearse restart, concurrent writes, and retention against a persistent test
  service with a controlled clock. Production WORM, lifecycle enforcement and
  IAM require a separate sandbox check before the owner deployment. Locking a
  production retention policy requires separate authorization.
