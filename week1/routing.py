"""Bounded local task routing before service history or evidence retrieval.

This is a rule parser, not a calibrated classifier. Unrecognized projections
and filters ask for clarification rather than silently changing the request.
"""

import re

from week1 import responses

_NEGATED = r"(?:do\s+not|don't|don’t|never)"
CHANGE_DETAILS = r"\b(?:timeout|retry|retries|cache|ttl|column|token|cipher|pool|nat|logging|flag|version|sender|worker|consumer|index|session|certificate)\b"


def active_request(question):
    # Quoted commands are examples, not requests to execute those commands.
    text = re.sub(r'"[^"\n]*"|“[^”\n]*”', "", question.lower())
    clauses = re.split(
        r"[;\n]|\b(?:but|instead)\b|,?\s+(?:and\s+)?(?=" + _NEGATED + r"\b)", text
    )
    return " ".join(
        clause.strip()
        for clause in clauses
        if not re.match(r"\s*(?:please\s+)?" + _NEGATED + r"\b", clause)
    )


def classify_scope(question, decision, services):
    """Classify supported CRA2 intents locally; history cannot supply scope."""
    if decision is not None:
        return "cra2"
    text = active_request(question)
    named_service = any(
        re.search(r"(?<![a-z0-9-])" + re.escape(name) + r"(?![a-z0-9-])", text)
        for name in services
    )
    detail = bool(re.search(CHANGE_DETAILS, text))
    change_context = (
        named_service
        or detail
        or bool(re.search(r"\b(?:this|that|the|proposed|planned)\s+change\b", text))
    )
    review = bool(re.search(r"\b(?:assess|evaluate|review|improve|risk|risky)\b", text))
    change = bool(
        re.search(r"\b(?:change|changing|set|increase|reduce|rollout|upgrade)\b", text)
    )
    history = bool(
        re.search(
            r"\b(?:had|caused|similar|past|previous)\b.*\bincidents?\b|"
            r"\bincidents?\b.*\b(?:before|history|past)\b",
            text,
        )
    )
    boundary = change_context and bool(
        re.search(
            r"\b(?:approve|authorize|merge|deploy|block)\b.*\b(?:for me|this change|it now)\b|\bjust approve\b",
            text,
        )
    )
    settings = bool(
        re.search(r"\bremember\b|\b(?:save|store)\b.*\bpreference", text)
    ) and (named_service or bool(re.search(r"\b(?:team|risk|freeze)\b", text)))
    operational_state = bool(re.search(r"\bfreeze\s+window\b", text)) or (
        (named_service or bool(re.search(r"\bservices?\b", text)))
        and bool(
            re.search(
                r"\bdepend(?:s|ents|encies)?\b|\b(?:current|live)\b.*\b(?:health|status)\b",
                text,
            )
        )
    )
    if (
        (change_context and (review or change))
        or (named_service and (detail or history or text.strip(" .?!") in services))
        or boundary
        or settings
        or operational_state
    ):
        return "cra2"
    return "non_cra2"


def task(question, catalog=None):
    """Return a browsing/help decision, clarification, or the assessment path."""
    catalog = catalog if catalog is not None else responses.load()
    text = active_request(question)
    browse = bool(re.search(r"\b(?:incidents?|scenarios?)\b", text)) and bool(
        re.search(
            r"\b(?:list|show|give|enumerate|count)\b|\bhow many\b|"
            r"\bnumber of\b|\b(?:what|which)\s+(?:risk\s+)?(?:incidents?|scenarios?)\b",
            text,
        )
    )
    assessment = bool(
        re.search(
            r"\bhow risky\b|\brisk of\b|\b(?:assess|evaluate|review)\b.{0,60}\b(?:risk|change)\b",
            text,
        )
    )
    operational = bool(
        re.search(
            r"\b(?:approve|authorize|merge|deploy|block|remember)\b|\b(?:save|store)\b.{0,40}\bpreference",
            text,
        )
    )
    agent = r"(?:cra2|change risk advisor|(?:this|the)\s+(?:agent|assistant)|you|your)"
    capability_word = (
        r"(?:capabilit(?:y|ies)|capabilties|capabilites|features?|functions?)"
    )
    capabilities = bool(
        re.search(
            r"\b"
            + agent
            + r"(?:'s)?\s+(?:(?:top|main|key|core|first|one|two|three|four|five|\d+)\s+)*"
            + capability_word
            + r"\b|\b"
            + capability_word
            + r"\s+(?:of|for|in)\s+"
            + agent
            + r"\b|\b"
            + capability_word
            + r"\s+(?:do|can)\s+you\s+(?:have|offer)\b",
            text,
        )
        or re.fullmatch(r"\s*(?:what are the )?" + capability_word + r"[?!. ]*", text)
    )
    capabilities = capabilities or bool(
        re.search(r"\bwhat\s+can\s+" + agent + r"\s+do\b", text)
    )
    if capabilities:
        # Incident nouns can describe a feature's subject. Require a separate
        # browsing command before treating that feature question as two tasks.
        browse = bool(
            re.search(
                r"\b(?:and|also|then)\s+(?:list|show|give|count)\b.{0,60}\b(?:incidents?|scenarios?)\b",
                text,
            )
        )
    help_request = (
        bool(
            re.search(
                r"\b(?:explain|describe)\s+(?:what\s+)?cra2(?:\s+(?:does|is|can do))?\s*(?:[?!.]|$)|"
                r"\bwhat\s+is\s+(?:cra2|(?:this|the)\s+(?:agent|assistant))\s*(?:[?!.]|$)|"
                r"\bwhat\s+does\s+(?:cra2|(?:this|the)\s+(?:agent|assistant))\s+do\b|"
                r"\bhow\s+(?:do i |to )?use\s+" + agent + r"\b|"
                r"\bwho\s+are\s+you\b|"
                r"^\s*(?:help|about cra2)[?!. ]*$",
                text,
            )
        )
        or capabilities
    )
    if help_request and (assessment or operational):
        return {
            "kind": "clarify",
            "question": responses.message(catalog, "help_or_change"),
        }
    if browse and (assessment or operational or help_request):
        return {
            "kind": "clarify",
            "question": responses.message(catalog, "browse_or_change"),
        }
    if help_request:
        if capabilities:
            requested = re.search(
                r"\b(?:top|first|list(?: me)?|show(?: me)?|give(?: me)?)\s+(\d+|one|two|three|four|five)\b",
                text,
            )
            total = len(catalog["capabilities"])
            count = total
            if requested:
                value = requested[1]
                count = (
                    int(value)
                    if value.isdigit()
                    else {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}[value]
                )
                if not 1 <= count <= total:
                    return {
                        "kind": "clarify",
                        "question": responses.message(
                            catalog,
                            "capability_limit",
                            total={
                                1: "one",
                                2: "two",
                                3: "three",
                                4: "four",
                                5: "five",
                            }.get(total, str(total)),
                        ),
                    }
            return {"kind": "help", "topic": "capabilities", "count": count}
        return {"kind": "help"}
    if not browse:
        if not text.strip() and re.search(
            _NEGATED + r"\s+(?:list|show|give|count|assess|review)\b", question.lower()
        ):
            return {
                "kind": "clarify",
                "question": responses.message(catalog, "missing_task"),
            }
        return None
    if re.search(
        r"\b(?:related to|similar to|matching|where|except|excluding)\b", text
    ):
        return {
            "kind": "clarify",
            "question": responses.message(catalog, "dataset_service_filter"),
        }
    operation = (
        "count" if re.search(r"\b(?:count|how many|number of)\b", text) else "list"
    )
    fields = []
    for field, pattern in (
        ("title", r"\b(?:titles?|names?)\b"),
        ("incident_id", r"\b(?:ids?|identifiers?)\b"),
        ("root_cause", r"\broot causes?\b"),
        ("severity", r"\bseverit(?:y|ies)\b"),
        ("service", r"\b(?:with|and) services?\b|\bservice names?\b"),
    ):
        if re.search(pattern, text):
            fields.append(field)
    if re.search(r"\b(?:details?|full records?)\b", text) and not re.search(
        r"\bno (?:other )?details?\b", text
    ):
        fields = ["title", "incident_id", "service", "root_cause", "severity"]
    if re.search(r"\b(?:dates?|owners?|impact|duration|timestamps?)\b", text):
        return {
            "kind": "clarify",
            "question": responses.message(catalog, "dataset_fields"),
        }
    if re.search(r"\b(?:titles?|names?)\s+only\b", text) and any(
        f != "title" for f in fields
    ):
        return {
            "kind": "clarify",
            "question": responses.message(catalog, "title_or_fields"),
        }
    if operation == "count" and re.search(r"\b(?:list|show|give|enumerate)\b", text):
        return {
            "kind": "clarify",
            "question": responses.message(catalog, "count_or_list"),
        }
    return {
        "kind": "browse",
        "operation": operation,
        "fields": fields or ["title"],
        "text": text,
    }


def service_scope(text, services):
    """Resolve a complete explicit filter; preserve unknown values for the caller."""
    match = re.search(r"\bfor\s+(.+)", text)
    if match:
        expression = re.split(
            r"[;?!]|\b(?:with|titles?|names?|root causes?|severity)\b",
            match[1],
            maxsplit=1,
        )[0]
        expression = re.sub(
            r"\b(?:in|from)\s+(?:the\s+)?(?:dataset|corpus|data set)\b.*",
            "",
            expression,
        )
        expression = re.sub(
            r"(?<![a-z0-9-])(?:the|service|services|only)(?![a-z0-9-])", "", expression
        ).strip(" .,:")
        if expression in {"all", "all known", "every"}:
            return set(), []
        candidates = [
            part.strip(" .,:") for part in re.split(r"\s+(?:and|or)\s+|,", expression)
        ]
        candidates = [part for part in candidates if part]
        if not candidates:
            return set(), ["unspecified service"]
    else:
        candidates = re.findall(r"\b[a-z0-9]+(?:-[a-z0-9]+)+\b", text)
        candidates += [
            name
            for name in services
            if re.search(r"(?<![a-z0-9-])" + re.escape(name) + r"(?![a-z0-9-])", text)
        ]
    # Inspect identifiers throughout the request too: a field clause must not
    # hide an unknown service that followed the first recognized filter.
    candidates += re.findall(r"\b[a-z0-9]+(?:-[a-z0-9]+)+\b", text)
    return set(candidates) & services, sorted(set(candidates) - services)
