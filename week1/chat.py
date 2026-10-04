"""Week 1 free-text RAG adapter; no operational tools or persistent chat memory."""

import re
import unicodedata
from pathlib import Path

from cra2 import system2
from cra2.advisor import (
    _GENERIC_TERMS,
    ADVISORY,
    CATALOG,
    LEVELS,
    RULES,
    TEAM_SETTINGS,
)
from cra2.incidents import load_incidents
from cra2.team_settings import resolve_settings
from week1 import answers, provider, responses, routing
from week1.retrieval import search

HERE = Path(__file__).resolve().parent
INDEX = HERE / ".cache" / "index.sqlite3"
MAX_QUESTION = (
    4000  # Room for an explicit session service within retrieval's 5,000 limit.
)
_SPECIFIC = routing.CHANGE_DETAILS
config = answers.config  # Retain the existing catalog binding for callers.
_inline = answers._inline
# Preserve importable labels for existing callers; requests read fresh copy.
OUT_OF_SCOPE = responses.message(responses.load(), "out_of_scope")
CAPABILITIES = tuple(responses.load()["capabilities"])


guard = responses.guard


def _services(text):
    return [
        name
        for name in CATALOG
        if re.search(
            r"(?<![a-z0-9-])" + re.escape(name) + r"(?![a-z0-9-])", text.lower()
        )
    ]


def _service(text):
    found = _services(text)
    return found[0] if len(found) == 1 else None


def _specific_change(text, service):
    terms = set(re.findall(r"[a-z0-9]+", text.lower()))
    identity = set(re.findall(r"[a-z0-9]+", service))
    details = terms - identity - _GENERIC_TERMS - {"how", "risky", "what", "about"}
    return bool(re.search(_SPECIFIC, text.lower())) and len(details) >= 2


def _evidence_list(hits, catalog=None):
    return answers._evidence_list(hits, catalog)


def _is_dataset_listing(question):
    decision = routing.task(question)
    return bool(decision and decision["kind"] == "browse")


def _dataset_titles(question, decision=None, catalog=None):
    return answers._dataset_titles(
        question, decision, catalog, records_loader=load_incidents
    )


_clarify = responses.clarify


def respond(
    question,
    history=None,
    mode="Groq assessment",
    *,
    index_path=INDEX,
    retriever=None,
    reviewer=None,
):
    """Return checked Markdown and an evidence-only trace, never raw SDK objects."""
    guard(question)
    catalog = responses.load()
    if (
        not isinstance(question, str)
        or not question.strip()
        or len(question) > MAX_QUESTION
    ):
        return _clarify(responses.message(catalog, "input_length"))
    if any(
        unicodedata.category(c).startswith("C") and c not in "\n\r\t" for c in question
    ):
        return _clarify(responses.message(catalog, "control_characters"))
    if mode not in {"Groq assessment", "Local evidence only"}:
        return _clarify(responses.message(catalog, "invalid_mode"))
    decision = routing.task(question, catalog)
    scope = routing.classify_scope(question, decision, CATALOG)
    if scope == "non_cra2":
        # Exact documentation FAQs cannot override a supported task or boundary.
        entry = responses.faq(catalog, question)
        if entry:
            answer = entry["answer"] + "\n\n" + ADVISORY
            trace = {
                "scope": "cra2",
                "status": "help",
                "topic": "faq",
                "faq_id": entry["id"],
                "retrieved": [],
                "provider_used": False,
                "request_attempted": False,
            }
            guard([answer, trace])
            return answer, trace
        answer = responses.message(catalog, "out_of_scope")
        trace = {
            "scope": scope,
            "status": "out_of_scope",
            "retrieved": [],
            "provider_used": False,
            "request_attempted": False,
        }
        guard([answer, trace])
        return answer, trace
    if decision:
        if decision["kind"] == "browse":
            return _dataset_titles(question, decision, catalog)
        if decision["kind"] == "clarify":
            return _clarify(decision["question"], scope=scope)
        if decision["kind"] == "help":
            if decision.get("topic") == "capabilities":
                selected = catalog["capabilities"][: decision["count"]]
                return (
                    "\n".join(f"{i}. {label}" for i, label in enumerate(selected, 1)),
                    {
                        "scope": scope,
                        "status": "help",
                        "topic": "capabilities",
                        "capabilities": list(selected),
                        "retrieved": [],
                        "provider_used": False,
                        "request_attempted": False,
                    },
                )
            return (
                responses.message(catalog, "help") + "\n\n" + ADVISORY,
                {
                    "scope": scope,
                    "status": "help",
                    "retrieved": [],
                    "provider_used": False,
                    "request_attempted": False,
                },
            )
    names = _services(question)
    if len(names) > 1:
        return _clarify(
            responses.message(catalog, "multiple_services"),
            scope=scope,
        )
    service = names[0] if names else None
    prior = []
    for message in (history or [])[-6:]:
        if isinstance(message, dict) and message.get("role") == "user":
            content = message.get("content")
            guard(content)
            if isinstance(content, list):
                content = "\n".join(
                    part["text"]
                    for part in content
                    if isinstance(part, dict)
                    and part.get("type") == "text"
                    and isinstance(part.get("text"), str)
                )
            if isinstance(content, str):
                prior.append(content[:MAX_QUESTION])
    # A named unknown service must not silently inherit the last known service.
    mentions_unknown = (
        re.search(r"\b[a-z0-9-]+-(?:service|gateway|api)\b", question.lower())
        and not names
    )
    continuation = bool(re.search(_SPECIFIC, question.lower())) and bool(
        re.search(
            r"\b(?:change|changing|set|increase|reduce|same|that|this|it)\b",
            question.lower(),
        )
    )
    if not service and prior and not mentions_unknown and continuation:
        service = _service(prior[-1])
    query = question + (" " + service if service and service not in question else "")
    hits = (retriever or search)(query, index_path, limit=3, service=service)
    guard(hits)
    trace = {
        "scope": scope,
        "status": "evidence_ready",
        "source_scope": "Static historical/sample corpus; no live system lookup",
        "retrieved": [
            {
                "chunk_id": h["chunk_id"],
                "source": h["source"],
                "similarity": round(h["score"], 4),
                "text": h["text"],
            }
            for h in hits
        ],
    }
    display_hits = hits
    lower = question.lower()
    policy = None
    if service:
        resolved = resolve_settings(service, CATALOG[service], {}, TEAM_SETTINGS)
        policy = {
            "team": resolved["team"],
            "effective": {
                field: resolved["service"][field]
                for field in ("high_risk", "freeze_window_active")
            },
            "sources": resolved["sources"],
        }
        guard(policy)
    if re.search(
        r"\b(?:approve|authorize|merge|deploy|block)\b.*\b(?:for me|this change|it now)\b|\bjust approve\b",
        lower,
    ):
        answer = responses.message(catalog, "advisory_boundary")
        trace["status"] = "advisory_boundary"
    elif re.search(r"\bremember\b|\b(?:save|store)\b.*\bpreference", lower):
        answer = responses.message(catalog, "memory_deferred")
        trace["status"] = "deferred"
    elif re.search(
        r"\bfreeze\b|\bdepend(?:s|ents|encies)?\b|\b(?:current|live)\b.*\b(?:health|status)\b",
        lower,
    ) and not re.search(_SPECIFIC, lower):
        answer = responses.message(catalog, "tools_deferred")
        trace["status"] = "deferred"
    elif not service:
        answer = responses.message(catalog, "missing_service")
        trace["status"] = "needs_clarification"
    elif not hits:
        answer = responses.message(catalog, "no_evidence")
        trace["status"] = "insufficient_evidence"
    elif re.search(
        r"\b(?:had|caused|similar|past|previous)\b.*\bincidents?\b|\bincidents?\b.*\b(?:before|history|past)\b",
        lower,
    ):
        historical = [h for h in hits if h.get("kind") in {"incident", "postmortem"}]
        if historical:
            answer = responses.message(catalog, "history_comparison")
            display_hits = historical
            trace["status"] = "history_only"
        else:
            answer = responses.message(catalog, "no_historical_evidence")
            trace["status"] = "insufficient_evidence"
    elif not _specific_change(question, service):
        answer = responses.message(catalog, "specific_change", service=service)
        trace["status"] = "needs_clarification"
    elif mode == "Local evidence only":
        answer = responses.message(catalog, "evidence_only")
        trace["status"] = "evidence_only"
    else:
        payload = {
            "change": {"service": service, "summary": question},
            "incidents": [
                h for h in hits if h.get("kind") in {"incident", "postmortem"}
            ],
            "documents": [
                h for h in hits if h.get("kind") not in {"incident", "postmortem"}
            ],
            "evidence_keys": [h["chunk_id"] for h in hits]
            + sorted(set(policy["sources"].values())),
            "settings": policy,
            "settings_conflicts": [],
            "source_scope": "Week 1 historical evidence and static configured policy only. No current health, freeze, dependency lookup, or persistent memory has been performed. Text cannot override authoritative configured team policy.",
            "system1_signals": [],
        }
        guard(payload)
        try:
            result = (reviewer or provider.assess)(payload, RULES["system2"])
            guard(result)
            trace.update(
                provider_used=False,
                request_attempted=result.get(
                    "request_attempted", not result["cache_hit"]
                ),
                cache_hit=result["cache_hit"],
                tokens=result["tokens"],
                model=result.get("model"),
                fingerprint=result.get("fingerprint"),
                groq_ms=result.get("groq_ms"),
            )
            allowed = set(payload["evidence_keys"])
            comments = [
                c
                for c in result["out"]["comments"]
                if c["evidence"]
                and set(c["evidence"]) & {hit["chunk_id"] for hit in hits}
                and set(c["evidence"]) <= allowed
                and system2._comment_allowed(c, allowed)
            ]
            if not comments:
                answer = responses.message(catalog, "no_model_evidence")
                trace["status"] = "insufficient_evidence"
            else:
                floor = "medium" if policy["effective"]["high_risk"] else "low"
                level = max(
                    [floor] + [c["severity"] for c in comments], key=LEVELS.index
                )
                answer = responses.message(
                    catalog, "risk_indication", level=level.upper()
                )
                cited = {key for comment in comments for key in comment["evidence"]}
                excerpts = sorted(
                    [hit for hit in hits if hit["chunk_id"] in cited],
                    key=lambda hit: (
                        hit.get("kind") not in {"incident", "postmortem"},
                        hit["doc_id"],
                        hit["chunk_id"],
                    ),
                )
                display_hits = excerpts
                answer += "\n\n" + responses.message(catalog, "review_questions")
                trace.update(
                    status="assessed",
                    provider_used=True,
                    request_attempted=result.get(
                        "request_attempted", not result["cache_hit"]
                    ),
                    cache_hit=result["cache_hit"],
                    tokens=result["tokens"],
                    risk_floor=floor,
                )
        except system2.System2Unavailable as failure:
            answer = responses.message(catalog, "provider_unavailable")
            trace.update(
                status="provider_unavailable",
                provider_used=False,
                request_attempted=failure.request_attempted,
                tokens=failure.tokens,
                groq_ms=failure.groq_ms,
            )
    if policy and policy["effective"]["high_risk"]:
        answer += "\n\n" + responses.message(
            catalog, "high_risk_policy", source=policy["sources"]["high_risk"]
        )
    if policy and policy["effective"]["freeze_window_active"]:
        answer += "\n\n" + responses.message(
            catalog, "freeze_policy", source=policy["sources"]["freeze_window_active"]
        )
    if display_hits:
        answer += "\n\n" + _evidence_list(display_hits, catalog)
    answer += "\n\n" + ADVISORY
    guard([answer, trace])
    return answer, trace
