"""Bounded local task routing before service history or evidence retrieval.

This is a rule parser, not a calibrated classifier. Unrecognized projections
and filters ask for clarification rather than silently changing the request.
"""

import re

_NEGATED = r"(?:do\s+not|don't|don’t|never)"


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


def task(question):
    """Return a browsing/help decision, clarification, or the assessment path."""
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
                r"\b(?:explain|describe)\s+(?:what\s+)?cra2\b|"
                r"\bwhat\s+(?:does|can|is)\s+cra2\b|\bhow\s+(?:do i |to )?use\s+"
                + agent
                + r"\b|"
                r"\bwho\s+are\s+you\b|\bwhat\s+(?:is|does)\s+(?:this|the)\s+(?:agent|assistant)\b|"
                r"^\s*(?:help|about cra2)[?!. ]*$",
                text,
            )
        )
        or capabilities
    )
    if help_request and (assessment or operational):
        return {
            "kind": "clarify",
            "question": "Choose one task: learn what CRA2 can do or review a proposed change. CRA2 cannot approve or execute changes.",
        }
    if browse and (assessment or operational or help_request):
        return {
            "kind": "clarify",
            "question": "Choose one task: browse the dataset or review a proposed change. CRA2 provides advice; a human makes the decision.",
        }
    if help_request:
        if capabilities:
            requested = re.search(
                r"\b(?:top|first|list(?: me)?|show(?: me)?|give(?: me)?)\s+(\d+|one|two|three|four|five)\b",
                text,
            )
            count = 5
            if requested:
                value = requested[1]
                count = (
                    int(value)
                    if value.isdigit()
                    else {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}[value]
                )
                if not 1 <= count <= 5:
                    return {
                        "kind": "clarify",
                        "question": "CRA2 has five implemented capability groups. Request one to five, or ask for the full list.",
                    }
            return {"kind": "help", "topic": "capabilities", "count": count}
        return {"kind": "help"}
    if not browse:
        if re.search(
            _NEGATED + r"\s+(?:list|show|give|count|assess|review)\b", question.lower()
        ):
            return {
                "kind": "clarify",
                "question": "What would you like CRA2 to do: browse incidents or review a proposed change?",
            }
        return None
    if re.search(
        r"\b(?:related to|similar to|matching|where|except|excluding)\b", text
    ):
        return {
            "kind": "clarify",
            "question": "For dataset browsing, specify exact service names. Describe the change separately to compare relevant historical incidents.",
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
            "question": "Choose supported dataset fields: title, incident ID, service, root cause, or severity.",
        }
    if re.search(r"\b(?:titles?|names?)\s+only\b", text) and any(
        f != "title" for f in fields
    ):
        return {
            "kind": "clarify",
            "question": "Do you want titles only, or titles with the additional incident fields?",
        }
    if operation == "count" and re.search(r"\b(?:list|show|give|enumerate)\b", text):
        return {
            "kind": "clarify",
            "question": "Would you like a count or a list of the dataset records?",
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
