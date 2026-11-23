"""Bounded intents for questions about recorded change evidence."""
import re

from cra2 import config
from cra2.incidents import load_incidents


def review_intent(text, catalog):
    ids = re.findall(r"\b(?:cx|inc)-\d+\b", text)
    if ids and re.search(r"\b(?:incident|service|affected|attributed)\b", text) and re.search(
            r"\b(?:was|were|did|which|what|where|who|is)\b", text):
        return "incident", list(dict.fromkeys(value.upper() for value in ids))
    if (re.search(r"\b(?:catalog|stored|recorded|snapshot)\b", text)
            and re.search(r"\b(?:health|healthy|degraded|status)\b", text)
            and named_services(text, catalog)):
        return "snapshot", []
    if re.search(r"\b(?:rollback|recovery|roll back)\b", text) and re.search(
            r"\b(?:what|which|how|evidence|runbook)\b", text):
        entities = re.findall(r"\b[\w]+(?:-[\w]+)*-(?:worker|service|api|gateway|frontend)\b", text)
        if entities:
            return "recovery", list(dict.fromkeys(entities))
    if (re.search(r"\b(?:raising|raise|increas(?:e|ing)|lower(?:ing)?|chang(?:e|ing))\s+"
                  r"(?:an? |the |our )?(?:(?:connection|rate|request|memory|concurrency) )?limit\b", text)
            and re.search(r"\b(?:verify|rollout|deployment|capacity|service|rate|request|concurrency)\b", text)):
        return "limit", []
    return None, []


def named_services(text, catalog):
    # Only match whole names or unique service stems within a recognized review question.
    names = set()
    for name in catalog:
        for alias in {name, name.removesuffix("-service")}:
            if re.search(r"(?<![\w-])" + re.escape(alias) + r"(?![\w-])", text):
                names.add(name)
    return sorted(names)


def incident_field(incident_id):
    for row in load_incidents(config.DATA_DIR):
        if row["incident_id"] == incident_id:
            filename = "incidents.json" if row["source_dataset"] == "synthetic" else "sample_incidents.json"
            return {"chunk_id": incident_id, "text": row["service"],
                    "source": f"data/{filename}#{incident_id}", "field": "service"}
    return None
