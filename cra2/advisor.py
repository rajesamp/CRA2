"""The CRA2 pipeline: change in -> classify -> assess risk -> thresholds -> route -> 3-comment summary."""

import json
import time

from cra2 import config, system1

RULES = json.loads((config.PKG_DIR / "rules.json").read_text())
CATALOG = json.loads((config.DATA_DIR / "checkout_system.json").read_text())["services"]
INCIDENTS = json.loads((config.DATA_DIR / "incidents.json").read_text())
LEVELS, ADVISORY = ["low", "medium", "high"], "This is advisory only. The decision to ship requires a human."


def context(change: dict) -> dict:
    """What both systems may use about this change: dict lookups on local files, no network."""
    if missing := {"service", "change_type", "summary"} - change.keys():
        raise ValueError(f"Change is missing: {', '.join(sorted(missing))}")
    if (name := change["service"]) not in CATALOG:
        raise ValueError(f"Unknown service {name!r}. Known: {', '.join(sorted(CATALOG))}")
    kind, svc, down, todo = change["change_type"], CATALOG[name], set(), [name]
    while todo:  # transitive dependents: everything that breaks if this service breaks
        new = {s for s, v in CATALOG.items() if todo[-1] in v["depends_on"]} - down
        down, todo = down | new, todo[:-1] + sorted(new)
    related = sorted((i for i in INCIDENTS if name == i["service"] or kind == i["change_type"]),
                     key=lambda i: (i["service"] != name, i["change_type"] != kind, i["incident_id"]))[:5]
    nearby, fields = [name, *svc["depends_on"]], [*change, "deploy_plan", "rollback_plan", "monitoring_plan"]
    evidence = ({f"change:{k}" for k in fields} | {f"catalog:{s}.{k}" for s in nearby for k in CATALOG[s]}
                | {f"graph:{name}.dependents", f"graph:{name}.depends_on"} | {i["incident_id"] for i in related})
    return {"name": name, "service": svc, "dependents": sorted(down), "related": related, "evidence": sorted(evidence),
            "repeats": [i for i in related if i["service"] == name and i["change_type"] == kind],
            "degraded": [s for s in nearby if CATALOG[s]["status"] != "Healthy"]}


def grade(score: float, tier: str, floor: str = "low") -> str:
    low, high = RULES["thresholds"][tier]
    return max("low" if score < low else "medium" if score < high else "high", floor, key=LEVELS.index)


def assess(change: dict, mode: str = config.MODE) -> dict:
    t0, ctx = time.perf_counter(), context(change)
    tier, s1 = ctx["service"]["tier"], system1.classify(change, ctx, RULES["system1"])
    floor = "high" if ctx["service"]["freeze_window_active"] else "medium" if ctx["degraded"] else "low"
    margin = min(round(abs(s1["score"] - t), 2) for t in RULES["thresholds"][tier])
    unsure = floor != "high" and margin < RULES["system1"]["confidence_margin"]
    score, comments, s2, note = s1["score"], s1["comments"], None, ""
    if mode == "deep" or (mode == "auto" and unsure):
        from cra2 import system2  # imported only when needed: the Groq SDK takes ~0.2 s to import
        payload = {"change": change, "service": {"name": ctx["name"], **ctx["service"]}, "incidents": ctx["related"],
                   "dependents": ctx["dependents"], "degraded": ctx["degraded"], "evidence_keys": ctx["evidence"],
                   "system1_signals": [c["text"] for c in s1["comments"] if c["weight"]]}
        try:
            s2 = system2.assess(payload, RULES["system2"])
            score = round((1 - (w := RULES["system2"]["weight"])) * score + w * s2["score"], 2)
            allowed = set(ctx["evidence"])  # grounding: drop any comment citing something it was not given
            grounded = [c for c in s2["out"]["comments"] if c["evidence"] and set(c["evidence"]) <= allowed]
            comments = sorted(grounded, key=lambda c: -LEVELS.index(c["severity"])) + comments
        except system2.ERRORS as exc:
            note = f"System 2 unavailable ({type(exc).__name__})."
    if unsure:  # paranoid: only a confident System 1 can put a change in the auto-approve lane, never the model
        floor = max(floor, "medium", key=LEVELS.index)
    top = [c for n, c in enumerate(comments) if c["tag"] not in {d["tag"] for d in comments[:n]}][:3]
    level = grade(score, tier, floor)
    return {"change_id": change.get("id", ""), "service": ctx["name"], "tier": tier, "level": level,
            "route": RULES["routes"][level], "score": score, "system1_score": s1["score"], "note": note,
            "path": "system2" if s2 else "system1", "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
            "comments": [{k: c[k] for k in ("tag", "severity", "text", "evidence")} for c in top],
            "system2": s2 and {k: s2[k] for k in ("score", "model", "fingerprint", "tokens", "groq_ms")}}


def render(r: dict) -> str:
    head = (f"**Risk: {r['level'].upper()}** (score {r['score']:.2f}, {r['tier']} tier) · recommended route: "
            f"**{r['route']}**\n_{r['path']} · {r['latency_ms']} ms{' · ' + r['note'] if r['note'] else ''}_")
    body = [f"{n}. [{c['tag']}] {c['text']} ({', '.join(c['evidence'])})" for n, c in enumerate(r["comments"], 1)]
    return "\n\n".join([head, "\n".join(body), ADVISORY])
