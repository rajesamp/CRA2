# Durable owner-only Cloud Run storage

The owner asked for durable memory and audit, with restart and retention tests.
The Cloud Run entrypoint currently uses instance-local SQLite. Keep the existing
IAP owner boundary and preserve the local stores and their files. Cloud state
starts empty for this first deployment. No local data transfer is in scope.
