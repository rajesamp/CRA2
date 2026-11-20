# Incident and rollback slice

The owner requested this work after Version 1. Add a protected read-only workspace
for incident analogues and rollback impact analysis over the existing approved
corpus. This first slice is a local prototype; production ingestion and rollback
execution are outside its scope.

Inputs: a catalog service, supported change type, bounded summary and proposed
rollback plan, plus explicit Unknown/Pass/Fail recovery declarations. Output:
source-attributed incident matches, recorded rollback approach, potential caller
exposure, downstream dependencies, blockers, missing evidence and next checks.

Preserve source identity and distinguish synthetic incidents from sanitized
samples. Exclude future-dated records from historical matching. Display the full
eligible-record denominator and returned-match count. Never infer an incident
rate from an incident-only corpus, causation from matching, or live health from
a snapshot. User declarations remain unverified, including Pass answers.

Reuse the verified principal and abuse admission boundary. No provider calls,
executable rollback, external connector, upload, dataset promotion, shared form
state or new identity grants. Reject malformed and secret-bearing input without
echo; source errors suppress the whole report. Escape all displayed source text.

Checks: direction/cycle-safe graph exposure, source IDs and matching reasons,
schema incompatibility, missing rehearsal and reconciliation evidence, future
records, unavailable/corrupt sources, invalid inputs, credential rejection,
markup injection, blocked admission, and an actual mounted UI callback.
