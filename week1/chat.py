"""Week 1 free-text RAG adapter; no operational tools or persistent chat memory."""

import os
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
    _inline,
)
from cra2.secrets import reject_credentials
from cra2.team_settings import resolve_settings
from week1 import provider
from week1.retrieval import search

HERE = Path(__file__).resolve().parent
INDEX = HERE / ".cache" / "index.sqlite3"
MAX_QUESTION = (
    4000  # Room for an explicit session service within retrieval's 5,000 limit.
)
_SPECIFIC = r"\b(?:timeout|retry|retries|cache|ttl|column|token|cipher|pool|nat|logging|flag|version|sender|worker|consumer|index|session|certificate)\b"


def guard(value):
    """Keep provider and optional UI-auth credentials out of application data."""
    reject_credentials(
        value, additional=(os.getenv("CRA2_UI_USER"), os.getenv("CRA2_UI_PASSWORD"))
    )


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


def _evidence_list(hits):
    """Show bounded, literal facts; retain full passages in the evidence trace."""
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
            label = "Guidance: " + label
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
    return "**Evidence · historical/sample**\n\n" + "\n".join(bullets)


def _clarify(text):
    return text + "\n\n" + ADVISORY, {"status": "needs_clarification", "retrieved": []}


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
    if (
        not isinstance(question, str)
        or not question.strip()
        or len(question) > MAX_QUESTION
    ):
        return _clarify("Please enter a change description of 1–4,000 characters.")
    if any(
        unicodedata.category(c).startswith("C") and c not in "\n\r\t" for c in question
    ):
        return _clarify("Please remove control characters from the request.")
    if mode not in {"Groq assessment", "Local evidence only"}:
        return _clarify("Choose Groq assessment or Local evidence only.")
    names = _services(question)
    if len(names) > 1:
        return _clarify(
            "Which one service is the target of this change? Assess one service at a time and describe its planned change."
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
        re.search(r"\b[a-z0-9-]+-(?:service|gateway)\b", question.lower()) and not names
    )
    if not service and prior and not mentions_unknown:
        service = _service(prior[-1])
    query = question + (" " + service if service and service not in question else "")
    hits = (retriever or search)(query, index_path, limit=3, service=service)
    guard(hits)
    trace = {
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
        answer = "I can help assess the change, but I cannot approve, block, merge, or deploy it. Please describe the planned change and a human can review the evidence."
        trace["status"] = "advisory_boundary"
    elif re.search(r"\bremember\b|\b(?:save|store)\b.*\bpreference", lower):
        answer = "This Week 1 demo does not store team preferences across sessions. Persistent team memory is a Week 2 task. You can include the preference in the current change description."
        trace["status"] = "week2_deferred"
    elif re.search(
        r"\bfreeze\b|\bdepend(?:s|ents|encies)?\b|\b(?:current|live)\b.*\b(?:health|status)\b",
        lower,
    ) and not re.search(_SPECIFIC, lower):
        answer = "I cannot confirm current freeze, health, or dependency state in Week 1. The corpus contains static examples and verification guidance; live tool calls are a Week 2 task. Treat current status as unconfirmed."
        trace["status"] = "week2_deferred"
    elif not service:
        answer = "Which catalog service is changing? Use an exact service name, such as checkout-service, and describe what will change. I will not infer a dependency or service identity from its name."
        trace["status"] = "needs_clarification"
    elif not hits:
        answer = "I found no supporting corpus evidence for this request. I cannot assign a risk indication without evidence. Please add the specific change and relevant incident context."
        trace["status"] = "insufficient_evidence"
    elif re.search(
        r"\b(?:had|caused|similar|past|previous)\b.*\bincidents?\b|\bincidents?\b.*\b(?:before|history|past)\b",
        lower,
    ):
        historical = [h for h in hits if h.get("kind") in {"incident", "postmortem"}]
        if historical:
            answer = "Past incidents for comparison; a match does not prove the same failure will recur."
            display_hits = historical
            trace["status"] = "history_only"
        else:
            answer = "The retrieved guidance contains no incident or postmortem supporting this comparison. Please describe the failure mechanism or change in more detail."
            trace["status"] = "insufficient_evidence"
    elif not _specific_change(question, service):
        answer = (
            "What specifically will change in "
            + service
            + "? Describe the affected setting or behavior and its before/after state. The retrieved history is context, not evidence that an unspecified change has the same failure mode."
        )
        trace["status"] = "needs_clarification"
    elif mode == "Local evidence only":
        answer = "Local evidence only; no model risk indication."
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
                answer = "The model returned no usable evidence-linked assessment. No risk indication is assigned; review the retrieved sources below."
                trace["status"] = "insufficient_evidence"
            else:
                floor = "medium" if policy["effective"]["high_risk"] else "low"
                level = max(
                    [floor] + [c["severity"] for c in comments], key=LEVELS.index
                )
                answer = (
                    "**Risk indication: "
                    + level.upper()
                    + "** — uncalibrated historical assessment. Current health is unverified."
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
                answer += "\n\n**Review questions**\n\n- Does this change repeat the cited failure mechanism?\n- How will recovery and monitoring be verified?"
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
            answer = "The model assessment is unavailable. No model risk indication is assigned. You can still review the retrieved historical evidence below."
            trace.update(
                status="provider_unavailable",
                provider_used=False,
                request_attempted=failure.request_attempted,
                tokens=failure.tokens,
                groq_ms=failure.groq_ms,
            )
    if policy and policy["effective"]["high_risk"]:
        answer += (
            "\n\nConfigured high-risk policy is retained; request text cannot override it. Source: "
            + policy["sources"]["high_risk"]
            + "."
        )
    if policy and policy["effective"]["freeze_window_active"]:
        answer += (
            "\n\nThe configured freeze report is unconfirmed. Verify applicability and exceptions with the team. Source: "
            + policy["sources"]["freeze_window_active"]
            + "."
        )
    if display_hits:
        answer += "\n\n" + _evidence_list(display_hits)
    answer += "\n\n" + ADVISORY
    guard([answer, trace])
    return answer, trace
