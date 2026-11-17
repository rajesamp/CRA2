# Implementation and test plan

1. Establish failing regression checks for cloud configuration, restart,
   generation conflicts and retention.
2. Build the minimal Cloud Storage JSON API adapters using locked HTTPX.
3. Inject stores through the cloud app and existing browser path. Keep the
   authorization boundary before routing and preserve local caller defaults.
4. Verify the real cloud mount with synthetic IAP plus the storage contract
   across processes. Run the Week 2–4 suite. Record cloud setup and rollback
   requirements without creating resources or locking production retention.
