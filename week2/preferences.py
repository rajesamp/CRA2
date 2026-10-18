"""Task 17: explicit preference commands and authoritative policy precedence."""

import re

from cra2.advisor import CATALOG, TEAM_SETTINGS
from cra2.team_settings import resolve_settings


def parse_command(question):
    patterns = (
        (r"remember(?: that)? ([a-z0-9-]+) is (?:always )?high[- ]risk(?: for our team)?[.!]?", "set"),
        (r"forget (?:the )?high[- ]risk preference for ([a-z0-9-]+)[.!]?", "clear"),
        (r"remember (?:the )?freeze(?:[- ]window)? policy for ([a-z0-9-]+): (.{1,500})", "note"),
    )
    if not isinstance(question, str):
        return None
    for pattern, kind in patterns:
        match = re.fullmatch(pattern, question.strip(), re.IGNORECASE)
        if match and match[1].lower() in CATALOG:
            return {"service": match[1].lower(), "updates":
                    {"freeze_notes": match[2].strip()} if kind == "note"
                    else {"high_risk": kind == "set"}}
    return None


def effective_policy(service, record, *, team_settings=None):
    settings = TEAM_SETTINGS if team_settings is None else team_settings
    preference = {} if record is None or record["high_risk"] is None else {"high_risk": record["high_risk"]}
    baseline = resolve_settings(service, CATALOG[service], {}, settings)
    resolved = resolve_settings(service, CATALOG[service], preference, settings)
    # Recalling a preference cannot weaken an existing catalog/team risk floor.
    if baseline["service"]["high_risk"] and not resolved["service"]["high_risk"]:
        resolved["service"]["high_risk"] = True
        resolved["sources"]["high_risk"] = baseline["sources"]["high_risk"]
        resolved["conflicts"].append({"field": "high_risk", "requested": False,
            "effective": True, "source": baseline["sources"]["high_risk"]})
    if resolved["sources"]["high_risk"] == "change:settings.high_risk":
        resolved["sources"]["high_risk"] = f"memory:{service}.high_risk"
    return {"team": resolved["team"],
            "effective": {key: resolved["service"][key] for key in ("high_risk", "freeze_window_active")},
            "sources": resolved["sources"], "conflicts": resolved["conflicts"]}
