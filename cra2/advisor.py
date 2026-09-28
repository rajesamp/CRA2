"""The CRA2 pipeline: change in -> classify -> assess risk -> thresholds -> route -> 3-comment summary."""

import json
import math
import re
import time
import unicodedata

from cra2 import config, system1
from cra2.incidents import load_incidents, normalize_change_type, select_incidents
from cra2.secrets import reject_credentials
from cra2.team_settings import load_settings, resolve_settings

RULES = json.loads((config.PKG_DIR / "rules.json").read_text())
CATALOG = json.loads((config.DATA_DIR / "checkout_system.json").read_text())["services"]
INCIDENTS = load_incidents(config.DATA_DIR)
TEAM_SETTINGS = load_settings(config.DATA_DIR, CATALOG)
LEVELS, ADVISORY = (
    ["low", "medium", "high"],
    "This is advisory only. The decision to ship requires a human.",
)
PLAN_FIELDS = ("deploy_plan", "rollback_plan", "monitoring_plan")
CHANGE_FIELDS = {"id", "service", "change_type", "summary", "settings", *PLAN_FIELDS}
SETTING_FIELDS = {"freeze_window_active", "high_risk"}
# This bounded lexical check catches generic requests. It is not an understanding
# model and cannot certify that a detailed-looking request is complete or true.
_GENERIC_TERMS = set(
    """a an the to of for on in with and or is are be it this that
    our my some please can could would should check assess risk risks change changes
    changing update updates updating upgrade upgrading deploy deployment roll rollout
    out release feature flag config configuration service services fix make do help
    new latest next minor small general routine something stuff tbd unknown details
    test testing validate validation needed perform improve improvement improvements
    soon today tomorrow production prod staging""".split()
)


def validate_change(change: dict) -> dict:
    """Return normalized, bounded input without mutating the caller's object."""
    if not isinstance(change, dict):
        raise ValueError("Change must be a JSON object.")
    reject_credentials(change)
    if change.keys() - CHANGE_FIELDS:
        raise ValueError("Change contains unsupported fields.")
    normalized = dict(change)
    if "settings" in change:
        settings = change["settings"]
        if (
            not isinstance(settings, dict)
            or settings.keys() - SETTING_FIELDS
            or any(type(value) is not bool for value in settings.values())
        ):
            raise ValueError(
                "Change settings must contain only boolean freeze_window_active/high_risk fields."
            )
        normalized["settings"] = dict(settings)
    for field in CHANGE_FIELDS - {"settings"}:
        value = change.get(field, "")
        if field in PLAN_FIELDS and value is None:
            value = ""
        if not isinstance(value, str):
            raise ValueError(f"Change field {field!r} must be a string.")
        if len(value) > 10_000:
            raise ValueError(f"Change field {field!r} exceeds 10,000 characters.")
        if any(
            unicodedata.category(char).startswith("C") and char not in "\t\n\r"
            for char in value
        ):
            raise ValueError(
                f"Change field {field!r} contains control or invisible formatting characters."
            )
        normalized[field] = value.strip()
    return normalized


def clarification_questions(change: dict) -> list[str]:
    """Ask for known identity and specific change content before any risk scoring."""
    questions = []
    if change["service"] not in CATALOG:
        questions.append(
            "Which catalog service is changing? Choose: "
            + ", ".join(sorted(CATALOG))
            + "."
        )
    if change["change_type"] not in RULES["system1"]["change_type"]:
        questions.append(
            "What type of change is planned? Choose: "
            + ", ".join(RULES["system1"]["change_type"])
            + "."
        )
    identity = set(
        re.findall(
            r"[a-z0-9]+", (change["service"] + " " + change["change_type"]).lower()
        )
    )
    details = (
        set(re.findall(r"[a-z0-9]+", change["summary"].lower()))
        - _GENERIC_TERMS
        - identity
    )
    if len({word for word in details if len(word) > 1 or word.isdigit()}) < 2:
        questions.append(
            "What specifically will change? Describe the affected behavior or component and its before/after state."
        )
    return questions


def _clarification(change: dict, questions: list[str], t0: float) -> dict:
    result = {
        "status": "needs_clarification",
        "change_id": change["id"],
        "service": change["service"],
        "tier": None,
        "level": None,
        "route": None,
        "score": None,
        "system1_score": None,
        "note": "",
        "system1_level": None,
        "risk_floor": None,
        "uncertain": True,
        "advisory": ADVISORY,
        "questions": questions,
        "freeze": None,
        "settings": None,
        "settings_conflicts": [],
        "incident_context": [],
        "system2_attempted": False,
        "system2_request_attempted": False,
        "system2_cache_hit": False,
        "system2_failure_usage": None,
        "path": "clarification",
        "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
        "comments": [],
        "system2": None,
    }
    reject_credentials(result)
    return result


def context(change: dict) -> dict:
    """What both systems may use about this change: dict lookups on local files, no network."""
    change = validate_change(change)
    if clarification_questions(change):
        raise ValueError("Change needs clarification before evidence retrieval.")
    name = change["service"]
    resolved = resolve_settings(
        name, CATALOG[name], change.get("settings", {}), TEAM_SETTINGS
    )
    kind, svc, down, todo = change["change_type"], resolved["service"], set(), [name]
    seen = {name}
    while todo:  # transitive dependents: everything that breaks if this service breaks
        current = todo.pop()
        new = {s for s, v in CATALOG.items() if current in v["depends_on"]} - seen
        seen.update(new)
        down.update(new)
        todo.extend(sorted(new))
    related = select_incidents(change, INCIDENTS)
    nearby, fields = (
        [name, *svc["depends_on"]],
        [*change, "deploy_plan", "rollback_plan", "monitoring_plan"],
    )
    evidence = (
        {f"change:{k}" for k in fields}
        | {f"catalog:{s}.{k}" for s in nearby for k in CATALOG[s]}
        | {f"graph:{name}.dependents", f"graph:{name}.depends_on"}
        | {i["incident_id"] for i in related}
    )
    for field, source in resolved["sources"].items():
        if source != f"catalog:{name}.{field}":
            evidence.discard(f"catalog:{name}.{field}")
    evidence.update(resolved["evidence"])
    return {
        "name": name,
        "settings": resolved,
        "service": svc,
        "dependents": sorted(down),
        "related": related,
        "evidence": sorted(evidence),
        "repeats": [
            i
            for i in related
            if i["service"] == name and normalize_change_type(i["change_type"]) == kind
        ],
        "degraded": [s for s in nearby if CATALOG[s]["status"] != "Healthy"],
    }


def grade(score: float, tier: str, floor: str = "low") -> str:
    if (
        isinstance(score, bool)
        or not isinstance(score, (int, float))
        or not math.isfinite(score)
        or not 0 <= score <= 1
    ):
        raise ValueError("Risk score must be a finite number between 0 and 1.")
    if tier not in RULES["thresholds"] or floor not in LEVELS:
        raise ValueError("Unknown risk tier or floor.")
    low, high = RULES["thresholds"][tier]
    return max(
        "low" if score < low else "medium" if score < high else "high",
        floor,
        key=LEVELS.index,
    )


def assess(change: dict, mode: str | None = None) -> dict:
    t0 = time.perf_counter()
    mode = config.MODE if mode is None else mode
    if mode not in ("fast", "auto", "deep"):
        raise ValueError("Mode must be fast, auto, or deep.")
    change = validate_change(change)
    if questions := clarification_questions(change):
        return _clarification(change, questions, t0)
    ctx = context(change)
    tier, s1 = ctx["service"]["tier"], system1.classify(change, ctx, RULES["system1"])
    # A reported freeze is unconfirmed context, never a block or risk floor.
    floor = "medium" if ctx["degraded"] or ctx["service"]["high_risk"] else "low"
    freeze = {
        "status": "unconfirmed"
        if ctx["service"]["freeze_window_active"]
        else "not_reported",
        "reported_active": ctx["service"]["freeze_window_active"],
        "evidence": [ctx["settings"]["sources"]["freeze_window_active"]],
    }
    questions = (
        [
            "Can the team confirm whether the reported freeze applies to this change and whether an exception is relevant?"
        ]
        if freeze["reported_active"]
        else []
    )
    settings = {
        "team": ctx["settings"]["team"],
        "effective": {field: ctx["service"][field] for field in sorted(SETTING_FIELDS)},
        "sources": ctx["settings"]["sources"],
    }
    margin = min(round(abs(s1["score"] - t), 2) for t in RULES["thresholds"][tier])
    unsure = floor != "high" and margin < RULES["system1"]["confidence_margin"]
    system1_level = grade(s1["score"], tier, floor)
    # A model may raise concern, but must never lower a deterministic risk assessment.
    floor = max(system1_level, "medium" if unsure else "low", key=LEVELS.index)
    score, comments, s2, note = s1["score"], s1["comments"], None, ""
    attempted = mode == "deep" or (mode == "auto" and unsure)
    request_attempted, cache_hit, failure_usage = False, False, None
    if attempted:
        from cra2 import (
            system2,
        )  # imported only when needed: the Groq SDK takes ~0.2 s to import

        payload = {
            "change": change,
            "service": {"name": ctx["name"], **ctx["service"]},
            "incidents": ctx["related"],
            "direct_dependencies": {
                name: CATALOG[name] for name in ctx["service"]["depends_on"]
            },
            "dependents": ctx["dependents"],
            "degraded": ctx["degraded"],
            "freeze": freeze,
            "settings": settings,
            "settings_conflicts": ctx["settings"]["conflicts"],
            "evidence_keys": ctx["evidence"],
            "system1_signals": [c["text"] for c in s1["comments"] if c["weight"]],
        }
        try:
            candidate = system2.assess(payload, RULES["system2"])
            allowed = set(
                ctx["evidence"]
            )  # grounding: drop any comment citing something it was not given
            grounded = [
                c
                for c in candidate["out"]["comments"]
                if c["evidence"] and set(c["evidence"]) <= allowed
            ]
            s2 = candidate
            request_attempted, cache_hit = s2["request_attempted"], s2["cache_hit"]
            score = round(
                (1 - (w := RULES["system2"]["weight"])) * score + w * s2["score"], 2
            )
            # Stable severity ordering keeps rule hazards ahead of equal-severity model prose.
            comments = sorted(
                comments + grounded, key=lambda c: -LEVELS.index(c["severity"])
            )
        except system2.ERRORS as exc:
            note = f"System 2 unavailable ({type(exc).__name__})."
            request_attempted = exc.request_attempted
            failure_usage = {"tokens": exc.tokens, "groq_ms": exc.groq_ms}
    top, seen_tags = [], set()
    for comment in comments:
        if comment["tag"] not in seen_tags:
            top.append(comment)
            seen_tags.add(comment["tag"])
        if len(top) == 3:
            break
    level = grade(score, tier, floor)
    result = {
        "status": "assessed",
        "questions": questions,
        "freeze": freeze,
        "settings": settings,
        "settings_conflicts": ctx["settings"]["conflicts"],
        "change_id": change.get("id", ""),
        "service": ctx["name"],
        "tier": tier,
        "level": level,
        "route": RULES["routes"][level],
        "score": score,
        "system1_score": s1["score"],
        "note": note,
        "system1_level": system1_level,
        "risk_floor": floor,
        "uncertain": unsure,
        "advisory": ADVISORY,
        "incident_context": ctx["related"],
        "system2_attempted": attempted,
        "system2_request_attempted": request_attempted,
        "system2_cache_hit": cache_hit,
        "system2_failure_usage": failure_usage,
        "path": "system2" if s2 else "system1",
        "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
        "comments": [
            {k: c[k] for k in ("tag", "severity", "text", "evidence")} for c in top
        ],
        "system2": s2
        and {
            k: s2[k]
            for k in (
                "score",
                "model",
                "fingerprint",
                "tokens",
                "groq_ms",
                "cache_hit",
                "request_attempted",
            )
        },
    }
    reject_credentials(result)
    return result


def _inline(text: str) -> str:
    """Keep untrusted plan/model text from adding terminal controls or Markdown structure."""
    text = " ".join(text.split())
    text = "".join(
        char for char in text if not unicodedata.category(char).startswith("C")
    )
    return re.sub(r"([\\`*\[\]<>_])", r"\\\1", text)


def render(r: dict) -> str:
    reject_credentials(r)
    if r["status"] == "needs_clarification":
        return "\n\n".join(
            [
                "**More detail needed before a risk assessment.**",
                "\n".join(
                    f"{n}. {_inline(q)}" for n, q in enumerate(r["questions"], 1)
                ),
                ADVISORY,
            ]
        )
    head = (
        f"**Risk: {r['level'].upper()}** (score {r['score']:.2f}, {r['tier']} tier) · review focus: "
        f"**{r['route']}**\n_{r['path']} · {r['latency_ms']} ms{' · ' + r['note'] if r['note'] else ''}_"
    )
    body = [
        f"{n}. [{c['tag']}] {_inline(c['text'])} ({', '.join(c['evidence'])})"
        for n, c in enumerate(r["comments"], 1)
    ]
    context_lines = []
    if r["freeze"]["reported_active"]:
        context_lines.append(
            "Freeze status: **unconfirmed** ("
            + ", ".join(r["freeze"]["evidence"])
            + ")."
        )
    if r["settings"]["effective"]["high_risk"]:
        context_lines.append(
            "Team risk context: high-risk service flag ("
            + r["settings"]["sources"]["high_risk"]
            + ")."
        )
    for conflict in r["settings_conflicts"]:
        context_lines.append(
            f"Setting conflict: {conflict['field']} requested {conflict['requested']}; "
            f"team setting {conflict['effective']} takes precedence ({conflict['source']})."
        )
    context_lines.extend(r["questions"])
    return "\n\n".join([head, "\n".join(body), *context_lines, ADVISORY])
