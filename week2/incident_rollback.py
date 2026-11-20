"""Read-only incident and recovery evidence; no model or execution capability."""
from datetime import date
from html import escape
import json

from cra2 import config
from cra2.incidents import load_incidents, select_incidents
from week2.tools import _context, _direction, _guard

CHANGE_TYPES = tuple(json.loads((config.PKG_DIR / "rules.json").read_text())["system1"]["change_type"])
CHECK_VALUES = ("Unknown", "Pass", "Fail")
RECONCILIATION_VALUES = ("Unknown", "Not needed", "Tested", "Untested")
FIELDS = ("service", "change_type", "summary", "rollback_plan", "compatibility", "rehearsal", "reconciliation")
EMPTY = {"status": "unavailable", "message": "Evidence could not be assessed. No readiness conclusion is available."}


def validate_inputs(values):
    if len(values) != len(FIELDS) or any(not isinstance(v, str) for v in values):
        raise ValueError("Invalid input")
    data = dict(zip(FIELDS, (v.strip() for v in values)))
    if (not 1 <= len(data["summary"]) <= 2000 or len(data["rollback_plan"]) > 1500
            or data["change_type"] not in CHANGE_TYPES
            or data["compatibility"] not in CHECK_VALUES or data["rehearsal"] not in CHECK_VALUES
            or data["reconciliation"] not in RECONCILIATION_VALUES
            or not 1 <= len(data["service"]) <= 200):
        raise ValueError("Invalid input")
    _guard(data)
    return data


def analyze(*values, as_of=None):
    """Produce bounded evidence, not a risk score or an approval decision."""
    try:
        data = validate_inputs(values)
    except (ValueError, TypeError):
        return {"status": "invalid_input", "message": "Input was not accepted. Check the form and omit credentials."}
    try:
        name, services = _context(data["service"], (), {})
        if len(services) > 200:
            raise ValueError("Catalog exceeds review bounds")
        record = services[name]
        approach = record.get("rollback")
        if not isinstance(approach, str) or not 1 <= len(approach) <= 2000:
            raise ValueError("Missing recovery evidence")
        for filename in ("incidents.json", "sample_incidents.json"):
            if (config.DATA_DIR / filename).stat().st_size > 1024 * 1024:
                raise ValueError("Incident source exceeds review bounds")
        history = load_incidents(config.DATA_DIR)
        _guard(history)
        if len(history) > 1000:
            raise ValueError("Incident count exceeds review bounds")
        today = date.today() if as_of is None else as_of
        eligible = [r for r in history if date.fromisoformat(r["date"]) <= today]
        matches = select_incidents(data, eligible, limit=5)
        for row in matches:
            filename = "incidents.json" if row["source_dataset"] == "synthetic" else "sample_incidents.json"
            row["evidence_ref"] = "data/" + filename + "#" + row["incident_id"]
        outgoing = {node: set(row["depends_on"]) for node, row in services.items()}
        incoming = {node: set() for node in services}
        for caller, dependencies in outgoing.items():
            for dependency in dependencies:
                incoming[dependency].add(caller)
        blockers, gaps, checks = [], [], []
        requirements = [
            ("compatibility", "Previous version compatibility", "Replay the previous binary against the proposed schema, configuration and event contracts."),
            ("rehearsal", "Recovery rehearsal", "Run an isolated recovery rehearsal; retain the artifact versions, result and measured recovery duration."),
            ("reconciliation", "State and side effects", "Account for writes, payments, emitted events and issued tokens; test reconciliation or document why none is needed."),
        ]
        for key, label, next_check in requirements:
            value = data[key]
            item = {"id": key, "label": label, "reported": value,
                    "provenance": "unverified_user_declaration", "evidence_ref": "declaration:" + key,
                    "next_check": next_check}
            checks.append(item)
            if value in {"Fail", "Untested"}:
                blockers.append(item)
            elif value == "Unknown":
                gaps.append(item)
        if not data["rollback_plan"]:
            gaps.append({"id": "rollback_plan", "label": "Proposed rollback plan is missing",
                         "next_check": "Specify the exact prior artifact/configuration, recovery trigger, responsible owner and stop conditions."})
        gaps += [
            {"id": "freshness", "label": "Current production state and dependency freshness are unknown",
             "next_check": "Confirm the graph and current service signals before using this recorded exposure analysis."},
            {"id": "verification", "label": "Form answers are declarations, not verified test evidence",
             "next_check": "Have a reviewer inspect the compatibility, recovery and reconciliation evidence."},
        ]
        result = {"status": "ok", "service": name, "change_type": data["change_type"],
                  "readiness": "reported_blockers" if blockers else "evidence_incomplete",
                  "execution_authorized": False, "provider_used": False,
                  "history": {"records_examined": len(history), "eligible_records": len(eligible),
                              "future_records_excluded": len(history) - len(eligible), "as_of": today.isoformat(),
                              "matches_returned": len(matches), "selection_limit": 5, "matches": matches,
                              "failure_rate": None, "limitation": "Incident-only corpus; successful-change denominator unavailable. Matches are not causal proof."},
                  "impact": {"potential_callers": _direction(name, incoming),
                             "dependencies_to_check": _direction(name, outgoing), "catalog_services_examined": len(services),
                             "source": "data/checkout_system.json", "kind": "synthetic_snapshot", "freshness": "unknown"},
                  "recorded_rollback": {"text": approach, "evidence_ref": "catalog:" + name + ".rollback",
                                        "measured_recovery_duration": None},
                  "checks": checks, "blockers": blockers, "gaps": gaps,
                  "human_decision_required": True}
        _guard(result)
        return result
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        return dict(EMPTY)


def render(report):
    """Escape every source-derived value; no source text becomes markup."""
    e = lambda value: escape(str(value), quote=True)
    if report.get("status") != "ok":
        return '<section role="status"><p>' + e(report.get("message", EMPTY["message"])) + '</p></section>'
    history, impact = report["history"], report["impact"]
    heading = "Reported rollback blockers" if report["blockers"] else "Recovery evidence is incomplete"
    parts = ['<section class="cra-recovery"><h2>' + heading + '</h2>',
             '<p><strong>' + e(report["service"]) + '</strong> · ' + e(report["change_type"]) +
             ' · Recorded evidence only · Human decision required</p>',
             '<h3>Historical incident evidence</h3><p>' + str(history["matches_returned"]) +
             ' related records shown (limit 5), from ' + str(history["eligible_records"]) + ' eligible records among ' +
             str(history["records_examined"]) + ' examined. ' + str(history["future_records_excluded"]) + ' future-dated records excluded.</p>']
    for row in history["matches"]:
        relationship = "Same-service history" if row["match_kind"] == "same_service_history" else "Cross-service analogue"
        parts += ['<article><h4>' + e(row["incident_id"]) + ' · ' + e(row["severity"]) + '</h4><p>' +
                  e(row["date"]) + ' · ' + e(row["service"]) + ' · ' + e(relationship) + '</p><p>' +
                  e(row["root_cause"]) + '</p><small>' + e(row["source_dataset"]) + ' · ' + e(row["evidence_ref"]) +
                  ' · Matched words: ' + e(", ".join(row["matched_terms"]) or "none; service identity match") + '</small></article>']
    if not history["matches"]:
        parts.append('<p>No related records were selected. This does not establish low risk.</p>')
    parts += ['<p>' + e(history["limitation"]) + '</p><h3>Recorded rollback approach</h3><p>' +
              e(report["recorded_rollback"]["text"]) + '</p><small>' + e(report["recorded_rollback"]["evidence_ref"]) +
              ' · Described timings are not measured recovery estimates.</small><h3>Potential rollback exposure</h3>']
    for label, nodes in (("Direct callers", impact["potential_callers"]["direct"]),
                         ("All reachable callers", impact["potential_callers"]["transitive"]),
                         ("Downstream dependencies to check", impact["dependencies_to_check"]["transitive"])):
        parts.append('<p><strong>' + label + ':</strong> ' + e(", ".join(nodes) or "None recorded") + '</p>')
    parts.append('<p>Potential propagation in the recorded graph, not observed impact. Source: ' + e(impact["source"]) + ' · Freshness unknown.</p>')
    parts.append('<h3>Recovery declarations</h3><ul>')
    for check in report["checks"]:
        parts.append('<li>' + e(check["label"]) + ': <strong>' + e(check["reported"]) + '</strong> · unverified declaration</li>')
    parts.append('</ul>')
    for title, items in (("Resolve reported blockers", report["blockers"]), ("Close evidence gaps", report["gaps"])):
        if items:
            parts.append('<h3>' + title + '</h3><ul>')
            for item in items:
                parts.append('<li><strong>' + e(item["label"]) + '</strong> — ' + e(item["next_check"]) + '</li>')
            parts.append('</ul>')
    parts.append('<p><strong>Analysis only. This report cannot authorize or execute a rollback.</strong></p></section>')
    return "".join(parts)


def guarded_analyze(values, *, gate, client):
    """Use the same server-owned abuse admission as chat; never echo failures."""
    try:
        if len(values) != len(FIELDS) or any(not isinstance(v, str) for v in values) or sum(map(len, values)) > 3900:
            raise ValueError("Invalid input")
        # Preserve field boundaries when the existing text screen normalizes
        # newlines; a service prefix must not conceal an action in another field.
        admission = gate.admit(".\n".join(values), client)
        if admission["blocked"]:
            result = {"status": "security_blocked", "message": "Request blocked. Wait for the temporary pause before trying again."}
        else:
            result = analyze(*values)
    except Exception:
        result = dict(EMPTY)
    return render(result), result


CSS = """
.cra-recovery { line-height:1.65; padding:12px; }
.cra-recovery h2 { color:#347b69; font-size:1.6rem; }
.cra-recovery h3 { margin-top:24px; }
.cra-recovery article { border-left:3px solid #66ab96; padding:8px 16px; margin:16px 0; background:rgba(91,158,138,.06); }
.cra-recovery small { opacity:.8; overflow-wrap:anywhere; }
"""
