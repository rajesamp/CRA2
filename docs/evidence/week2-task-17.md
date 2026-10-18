# Task 17: automatic cross-session preference recall

Executed in three separate Python processes with a persistent SQLite store.
No model/provider was called. Session B supplied no history or preference text.

## Session A: explicit write

```json
{
  "session_id": "4a72d178762147c4bfe335584678f506",
  "query": "Remember that checkout-service is always high-risk for our team.",
  "status": "memory_saved",
  "memory": {
    "status": "recalled",
    "record": {
      "team": "sample-team",
      "service": "checkout-service",
      "high_risk": true,
      "freeze_notes": null,
      "updated_at": "2026-10-18T03:21:51.004098+00:00",
      "source": "explicit_team_preference"
    },
    "effective_policy": {
      "team": "sample-team",
      "effective": {
        "high_risk": true,
        "freeze_window_active": false
      },
      "sources": {
        "freeze_window_active": "catalog:checkout-service.freeze_window_active",
        "high_risk": "memory:checkout-service.high_risk"
      },
      "conflicts": []
    }
  },
  "mcp_calls": []
}
```

## Session B: automatic recall

```json
{
  "session_id": "b8771dffa9db4c809b13524cc8bb2d8c",
  "query": "Change checkout-service config timeout from 4 seconds to 400 milliseconds.",
  "status": "evidence_only",
  "memory": {
    "status": "recalled",
    "record": {
      "team": "sample-team",
      "service": "checkout-service",
      "high_risk": true,
      "freeze_notes": null,
      "updated_at": "2026-10-18T03:21:51.004098+00:00",
      "source": "explicit_team_preference"
    },
    "effective_policy": {
      "team": "sample-team",
      "effective": {
        "high_risk": true,
        "freeze_window_active": false
      },
      "sources": {
        "freeze_window_active": "catalog:checkout-service.freeze_window_active",
        "high_risk": "memory:checkout-service.high_risk"
      },
      "conflicts": []
    }
  },
  "mcp_calls": [
    "check_system_health",
    "get_dependency_graph"
  ]
}
```

## Different-team control

```json
{
  "session_id": "8ed3ca3a88974f268a37d9624087d672",
  "query": "What services depend on checkout-service?",
  "status": "tool_evidence",
  "memory": {
    "status": "empty",
    "record": null,
    "effective_policy": {
      "team": "sample-team",
      "effective": {
        "high_risk": false,
        "freeze_window_active": false
      },
      "sources": {
        "freeze_window_active": "catalog:checkout-service.freeze_window_active",
        "high_risk": "default:high_risk"
      },
      "conflicts": []
    }
  },
  "mcp_calls": [
    "get_dependency_graph"
  ]
}
```

The guarded full transcripts are local under ignored `week2/.local/task17-sessions.json`.
High-risk recall is a team policy flag; local evidence mode emits no model risk rating.
Configured policy remains authoritative. Freeze notes are inert reminders, not observed status.
