"""Category findings resolved only against one recovery review's evidence."""
from datetime import date
from html import escape

from week2.release_info import digest
from week2.presentation import freeze_window_summary


CATEGORIES = (
    ("Technical", "Direct technical exposure is unknown.", "Which calls or components use the changed setting?"),
    ("Operational", "Rollout signals are unknown.", "Which threshold and observation window would stop the rollout?"),
    ("Business", "Customer and financial exposure are unknown.", "Which customer journey and measure will the owner check?"),
    ("Security and compliance", "Access and data-handling impact are unknown.",
     "Does the proposal change a protected boundary or the classification of data it handles?"),
)


def snapshot(review_id, service, record, matches, freeze):
    sources = {}
    refs = {title: [] for title, _, _ in CATEGORIES}

    def add(category, ref, kind, value, observed=None):
        sources[ref] = {"category": category, "kind": kind, "value": value, "observed": observed}
        refs[category].append(ref)

    observed = record.get("observed_at")
    if observed is not None:
        observed = date.fromisoformat(observed).isoformat()
    catalog = f"catalog:{service}."
    add("Technical", catalog + "depends_on", "Recorded direct dependencies",
        record["depends_on"], observed)
    monitors = record.get("monitors")
    if monitors is not None:
        if not isinstance(monitors, list) or len(monitors) > 64 or not all(
                isinstance(item, str) and 0 < len(item.strip()) <= 200 for item in monitors):
            raise ValueError("Invalid catalog monitors")
        if monitors:
            add("Operational", catalog + "monitors", "Recorded monitors", monitors, observed)
    for row in matches:
        kind = ("Same-service historical incident" if row["match_kind"] == "same_service_history"
                else "Cross-service historical analogue")
        add("Technical", row["evidence_ref"], kind, row["service"] + " · " + row["incident_id"], row["date"])
    if freeze:
        add("Operational", catalog + "freeze_window_active", "Freeze window",
            freeze_window_summary(freeze["recorded_flag"]), observed)
        add("Operational", "declaration:summary", "Unverified operator declaration", freeze["declaration"])

    # Include the selected incident records in the version even if the card
    # only names the incident. A corrected incident must invalidate its citation.
    version = digest([service, sources, matches])
    return {"review_id": review_id, "version": version, "sources": sources,
            "cards": [{"review_id": review_id, "version": version, "refs": keys} for keys in refs.values()]}


def render(report):
    snapshot = report["risk_categories"]
    version = snapshot["version"]
    sources = snapshot["sources"]
    current = (snapshot["review_id"] == report["request_id"] and
               version == digest([report["service"], sources, report["history"]["matches"]]))
    parts = ['<section class="cra-risk-categories"><h3>Risk by category</h3>']
    for (title, gap, question), card in zip(CATEGORIES, snapshot["cards"], strict=True):
        parts.append(f"<article><h4>{title}</h4>")
        card_current = current and card["version"] == version and card["review_id"] == report["request_id"]
        resolved = [ref for ref in card["refs"] if ref in sources and sources[ref]["category"] == title] if card_current else []
        if not resolved:
            parts.append(f"<p><strong>Evidence gap</strong> · {gap}</p>")
        for ref in resolved:
            item = sources[ref]
            when = "Observed " + item["observed"] if item["observed"] else "Freshness unknown"
            value = item["value"]
            if isinstance(value, list):
                value = ", ".join(value) or "None listed in the snapshot"
            parts.append(f"<p><strong>{escape(item['kind'])}</strong> · {escape(value)}<br>"
                         f"<small>{escape(ref)} · {escape(when)} · Evidence {escape(version[:12])}</small></p>")
        if "declaration:summary" in resolved:
            question = "How does the operator’s declaration compare with the recorded freeze flag, and who can confirm the current window?"
        parts.append(f"<p>{question}</p></article>")
    return "".join(parts) + "</section>"
