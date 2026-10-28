# Week 2 team-preference memory

Schema version 1 stores preferences, not conversations. The trusted local host
chooses the team from configured team settings. No chat text or browser input
can select a team, database path, SQL query or policy file.

| Field | Meaning |
|---|---|
| team, service | Composite primary key; service must be in the catalog |
| high_risk | Nullable boolean preference; omitted means retain previous value |
| freeze_notes | Nullable bounded plain text, at most 500 characters |
| updated_at | UTC timestamp of the explicit preference write |
| source | Fixed `explicit_team_preference` provenance |

The SQLite database has a checked application ID and `user_version=1`. The
default is ignored `week2/.local/team-memory.sqlite3`; constructor paths are
limited to the repository or `/tmp`. New files use mode 0600. Reads of absent
storage return no record without creating it; corrupted, locked, oversized or
unrecognized storage fails with `memory_unavailable`. Existing unrelated files
are never silently initialized or migrated. No conversations, provider keys,
SDK objects, prompts or hidden reasoning are stored.

Writes use parameterized SQL and atomic upserts. Team and service lookups are
scoped on every read/write. This is a single-team local demo, not a claim of
production multi-user authentication. Persistent chat history stays deferred.

Configured policy remains authoritative, including explicitly false fields.
Stored preferences cannot silently weaken it; conflicts are shown. A recalled
high-risk flag retains the existing medium minimum assessment floor. Local
evidence mode still assigns no model risk rating. Freeze notes are inert policy
reminders and never establish an active freeze; they are not model instructions.
