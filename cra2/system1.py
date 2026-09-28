"""System 1: deterministic rule-based scoring and evidence-linked comments, with no network."""


def classify(change: dict, ctx: dict, w: dict) -> dict:
    """Score a change 0-1 with the rules.json weights. Each rule that fires gives one grounded comment;
    zero-weight rules add fallback comments, so there are always at least three."""
    name, svc, down, repeats = (
        ctx["name"],
        ctx["service"],
        ctx["dependents"],
        ctx["repeats"],
    )
    plan = {
        k: (change.get(k) or "").strip().rstrip(".").rstrip()
        for k in ("rollback_plan", "monitoring_plan", "deploy_plan")
    }
    facts = {
        **svc,
        **plan,
        "name": name,
        "watch": ", ".join(svc["monitors"]),
        "down": ", ".join(down) or "none",
        "n_down": len(down),
        "degraded": ", ".join(ctx["degraded"]),
        "repeats": "; ".join(
            f"{i['incident_id']} ({i['root_cause']})" for i in repeats
        ),
    }
    rules = [  # (fires, weight, comment key in rules.json, evidence)
        (
            svc["freeze_window_active"],
            w["freeze"],
            "freeze",
            [ctx["settings"]["sources"]["freeze_window_active"]],
        ),
        (
            repeats,
            min(w["per_repeat_incident"] * len(repeats), w["repeat_cap"]),
            "history",
            [i["incident_id"] for i in repeats],
        ),
        (
            not plan["rollback_plan"],
            w["no_rollback_plan"],
            "no_rollback",
            ["change:rollback_plan", f"catalog:{name}.rollback"],
        ),
        (
            not plan["monitoring_plan"],
            w["no_monitoring_plan"],
            "no_monitoring",
            ["change:monitoring_plan", f"catalog:{name}.monitors"],
        ),
        (
            change["change_type"] == "Config change" and svc["config_drift_prone"],
            w["config_drift"],
            "config_drift",
            [f"catalog:{name}.config_source"],
        ),
        (
            not plan["deploy_plan"] and down,
            w["no_deploy_plan"],
            "no_deploy_plan",
            ["change:deploy_plan", f"graph:{name}.dependents"],
        ),
        (
            ctx["degraded"],
            w["degraded"],
            "degraded",
            [f"catalog:{s}.status" for s in ctx["degraded"]],
        ),
        (plan["rollback_plan"], 0, "rollback", ["change:rollback_plan"]),
        (
            plan["monitoring_plan"],
            0,
            "monitoring",
            ["change:monitoring_plan", f"catalog:{name}.monitors"],
        ),
        (True, 0, "dependencies", [f"graph:{name}.dependents"]),
    ]
    fired = sorted((r for r in rules if r[0]), key=lambda r: (r[2] != "freeze", -r[1]))
    score = (
        w["change_type"][change["change_type"]]
        + w["tier"][svc["tier"]]
        + min(w["per_dependent"] * len(down), w["dependents_cap"])
        + sum(r[1] for r in fired)
    )
    comments = [
        {
            "tag": w["comments"][key]["tag"],
            "text": w["comments"][key]["text"].format(**facts),
            "weight": wt,
            "severity": "high" if wt >= 0.2 else "medium" if wt else "low",
            "evidence": ev,
        }
        for _, wt, key, ev in fired
    ]
    return {"score": round(min(score, 1.0), 2), "comments": comments}
