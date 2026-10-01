"""Evidence and dataset answers backed by canonical facts, not FAQ copy."""

import hashlib
import json
import re
from pathlib import Path

from cra2 import config
from cra2.advisor import CATALOG, _inline
from cra2.incidents import load_incidents
from week1 import responses, routing
from week1.responses import clarify as _clarify
from week1.responses import guard

HERE = Path(__file__).resolve().parent


def _evidence_list(hits, catalog=None):
    """Show bounded, literal facts; retain full passages in the evidence trace."""
    catalog = catalog if catalog is not None else responses.load()
    bullets = []
    seen = set()
    for hit in hits:
        text = hit["text"]
        brief = ""
        if hit.get("kind") == "incident" and "Root cause:" in text:
            brief = text.split("Root cause:", 1)[1].strip()
        elif "## Recorded facts" in text:
            facts = text.split("## Recorded facts", 1)[1]
            # The corpus separates recorded facts from unknowns and review checks.
            brief = re.split(r"\s+(?=The fixture\b|##\s)", facts.strip(), maxsplit=1)[0]
            if not brief.endswith((".", "!", "?")):
                brief = ""  # A chunk boundary may cut a sentence short.
        elif (
            not text.startswith("#")
            and not re.search(r"#chunk-(?!001$)\d+$", hit["chunk_id"])
            and hit.get("kind") != "runbook"
        ):
            brief = text if text.endswith((".", "!", "?")) else ""
        # Never truncate a fact mid-sentence or remove its qualifiers.
        if len(brief.split()) > 55:
            brief = ""
        brief = brief.replace("**", "")
        label = brief or hit.get("title", hit["doc_id"])
        if hit.get("kind") == "runbook":
            label = responses.message(catalog, "guidance_prefix") + label
        identity = (hit["doc_id"], label)
        if identity in seen:
            continue
        seen.add(identity)
        bullets.append(
            "- "
            + _inline(label).replace("#", "\\#")
            + " ("
            + _inline(hit["chunk_id"])
            + ")"
        )
    return responses.message(catalog, "evidence_heading") + "\n\n" + "\n".join(bullets)


def _dataset_titles(
    question, decision=None, catalog=None, *, records_loader=load_incidents
):
    # Curated labels are bound to the canonical facts; reject stale mappings.
    catalog = catalog if catalog is not None else responses.load()
    records = records_loader(config.DATA_DIR)
    guard(records)
    titles = json.loads((HERE / "scenario_titles.json").read_text(encoding="utf-8"))
    guard(titles)
    if set(titles) != {record["incident_id"] for record in records}:
        raise ValueError("Scenario titles do not match the incident corpus")
    for record in records:
        entry = titles[record["incident_id"]]
        if (
            entry["root_cause_sha256"]
            != hashlib.sha256(record["root_cause"].encode()).hexdigest()
            or not isinstance(entry["title"], str)
            or not entry["title"].strip()
            or len(entry["title"]) > 120
        ):
            raise ValueError("Scenario title requires source review")
    decision = decision or routing.task(question, catalog)
    services = set(CATALOG) | {record["service"] for record in records}
    requested, unresolved = routing.service_scope(decision["text"], services)
    if unresolved:
        answer, trace = _clarify(
            responses.message(
                catalog,
                "unknown_dataset_service",
                services=", ".join(_inline(name) for name in unresolved),
            ),
            scope="cra2",
        )
        trace.update(
            unresolved_scope=unresolved,
            scenarios=[],
            provider_used=False,
            request_attempted=False,
        )
        guard([answer, trace])
        return answer, trace
    selected = [
        record for record in records if not requested or record["service"] in requested
    ]
    scenarios = {}
    for record in selected:
        title = titles[record["incident_id"]]["title"]
        filename = (
            "incidents.json"
            if record["source_dataset"] == "synthetic"
            else "sample_incidents.json"
        )
        scenarios.setdefault(title, []).append(
            {
                "incident_id": record["incident_id"],
                "service": record["service"],
                "source_dataset": record["source_dataset"],
                "source": "data/" + filename + "#" + record["incident_id"],
            }
        )
    answer = "\n".join("- " + _inline(title).replace("#", "\\#") for title in scenarios)
    if decision["operation"] == "count":
        if re.search(r"\b(?:distinct|unique)\b", decision["text"]):
            answer = responses.message(
                catalog, "distinct_title_count", count=len(scenarios)
            )
        else:
            answer = responses.message(catalog, "incident_count", count=len(selected))
    elif decision["fields"] != ["title"]:
        labels = catalog["field_labels"]
        answer = "\n".join(
            "- "
            + "; ".join(
                _inline(titles[record["incident_id"]]["title"])
                if field == "title"
                else labels[field] + ": " + _inline(record[field])
                for field in decision["fields"]
            )
            for record in selected
        )
    trace = {
        "scope": "cra2",
        "status": "dataset_count"
        if decision["operation"] == "count"
        else "dataset_listing",
        "provider_used": False,
        "request_attempted": False,
        "retrieved": [],
        "source_scope": "Canonical synthetic incidents and sanitized samples; no live system lookup",
        "title_basis": "Curated scenario titles checked against source hashes; identical labels grouped",
        "operation": decision["operation"],
        "requested_fields": decision["fields"],
        "record_count": len(selected),
        "distinct_title_count": len(scenarios),
        "service_filter": sorted(requested),
        "scenarios": [
            {"title": title, "sources": sources} for title, sources in scenarios.items()
        ],
    }
    guard([answer, trace])
    return answer or responses.message(catalog, "no_scenarios"), trace
