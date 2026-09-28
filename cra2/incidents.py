"""Validated incident history and bounded, deterministic contextual retrieval."""

import json
import re
import unicodedata
from datetime import date
from functools import lru_cache
from pathlib import Path

_FIELDS = {"incident_id", "service", "date", "change_type", "severity", "root_cause"}
_STOP_WORDS = {
    "the",
    "and",
    "for",
    "from",
    "with",
    "this",
    "that",
    "these",
    "those",
    "was",
    "were",
    "are",
    "has",
    "had",
    "have",
    "not",
    "but",
    "into",
    "due",
    "after",
    "before",
    "during",
    "through",
    "then",
    "than",
    "only",
    "all",
    "change",
    "deployment",
    "deploy",
    "service",
    "plan",
    "check",
    "previous",
    "caused",
    "cause",
    "leading",
    "led",
    "issue",
    "result",
    "resulted",
}


def normalize_change_type(value: str) -> str:
    """Use an explicit matching alias without rewriting a source incident."""
    return "Code deploy" if value == "Deployment" else value


def load_incidents(data_dir: Path) -> list[dict]:
    """Load both bundled corpora, failing explicitly on invalid or duplicate data."""
    incidents, seen = [], set()
    for filename, dataset in (
        ("incidents.json", "synthetic"),
        ("sample_incidents.json", "sanitized_samples"),
    ):
        records = json.loads((data_dir / filename).read_text(encoding="utf-8"))
        if not isinstance(records, list) or not records:
            raise ValueError(f"{filename} must contain a nonempty incident array")
        for index, record in enumerate(records):
            label = f"{filename} record {index + 1}"
            if not isinstance(record, dict) or not _FIELDS <= record.keys():
                raise ValueError(f"{label} is missing required incident fields")
            if record.keys() - (_FIELDS | {"source"}):
                raise ValueError(f"{label} contains unsupported incident fields")
            for field, value in record.items():
                if not isinstance(value, str) or not value.strip() or len(value) > 2000:
                    raise ValueError(
                        f"{label} field {field!r} must be a bounded nonempty string"
                    )
                if any(unicodedata.category(char).startswith("C") for char in value):
                    raise ValueError(
                        f"{label} field {field!r} contains control characters"
                    )
            if date.fromisoformat(record["date"]).isoformat() != record["date"]:
                raise ValueError(f"{label} date must use YYYY-MM-DD")
            if record["severity"] not in {"SEV1", "SEV2", "SEV3", "SEV4"}:
                raise ValueError(f"{label} severity must be SEV1, SEV2, SEV3, or SEV4")
            if record["incident_id"] in seen:
                raise ValueError(f"{label} duplicates an incident ID")
            seen.add(record["incident_id"])
            incidents.append({**record, "source_dataset": dataset})
    return incidents


def _terms(text: str) -> set[str]:
    """Match words (including technical abbreviations), without semantic claims."""
    terms = set()
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        # Simple plural normalization allows 'queries'/'query' and 'errors'/'error'.
        if len(token) > 4 and token.endswith("ies"):
            token = token[:-3] + "y"
        elif len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        if len(token) >= 3 and token not in _STOP_WORDS:
            terms.add(token)
    return terms


@lru_cache(maxsize=512)
def _incident_terms(service: str, root_cause: str) -> frozenset[str]:
    """Reuse tokenized history while including its actual content in the key."""
    return frozenset(_terms(service + " " + root_cause))


def select_incidents(change: dict, incidents: list[dict], limit: int = 5) -> list[dict]:
    """Prioritize target-service history, then relevant cross-service analogues.

    A foreign service is never an alias for a catalog service. Matching terms
    and equivalent change types are retrieval signals, not proof of causation.
    """
    query = _terms(
        " ".join(
            change.get(field, "") or ""
            for field in (
                "service",
                "summary",
                "deploy_plan",
                "rollback_plan",
                "monitoring_plan",
            )
        )
    )
    candidates = []
    for incident in incidents:
        same_service = incident["service"] == change["service"]
        same_type = (
            normalize_change_type(incident["change_type"]) == change["change_type"]
        )
        overlap = query & _incident_terms(incident["service"], incident["root_cause"])
        if not (same_service or len(overlap) >= 2):
            continue
        group = 0 if same_service and same_type else 1 if same_service else 2
        rank = (
            group,
            -len(overlap),
            not same_type,
            -date.fromisoformat(incident["date"]).toordinal(),
            incident["incident_id"],
        )
        candidates.append(
            (
                rank,
                {
                    **incident,
                    "match_kind": "same_service_history"
                    if same_service
                    else "cross_service_analogue",
                    "matched_terms": sorted(overlap),
                },
            )
        )
    return [
        record
        for _, record in sorted(candidates, key=lambda candidate: candidate[0])[:limit]
    ]
