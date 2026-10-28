# Task 16: persistent preference schema and readback

A real SQLite write and fresh-process readback were executed; no provider was called.

```json
{
  "executed_at": "2026-10-18T03:17:54.518160+00:00",
  "written": {
    "team": "learning-team",
    "service": "checkout-service",
    "high_risk": true,
    "freeze_notes": "Verify the team freeze calendar before review.",
    "updated_at": "2026-10-18T03:17:54.119522+00:00",
    "source": "explicit_team_preference"
  },
  "read_in_fresh_process": {
    "team": "learning-team",
    "service": "checkout-service",
    "high_risk": true,
    "freeze_notes": "Verify the team freeze calendar before review.",
    "updated_at": "2026-10-18T03:17:54.119522+00:00",
    "source": "explicit_team_preference"
  },
  "equal": true
}
```

The store is ignored under `week2/.local/`. Schema and limits: [memory.md](../memory.md).
Memory stores explicit team preferences only, not conversations or observed freeze state.
