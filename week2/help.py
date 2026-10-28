"""Local onboarding intents; operational requests keep their existing routes."""

import re

from week1.routing import active_request


def admin_navigation(question):
    """A whole navigation question, never an appended action on private data."""
    return isinstance(question, str) and bool(re.fullmatch(
        r"\s*(?:how (?:do i |can i |to )?(?:open|find|use|unlock)|where (?:is|can i find)) "
        r"(?:the )?admin(?: (?:tab|panel))?\s*[?.!]?\s*", question, re.IGNORECASE))


def help_topic(question, decision, services):
    text = active_request(question)
    if decision and decision["kind"] != "help":
        return None
    if re.match(r"\s*(?:please\s+)?(?:remember|forget|save|store|approve|authorize|merge|deploy|block)\b", text):
        return None
    if re.search(r"\bhow risky\b|\brisk of\b|\b(?:assess|evaluate|review)\b.{0,60}\b(?:risk|change)\b", text):
        return None
    app = bool(re.search(r"\bcra2\b|\bchange[ -]risk advisor\b|\b(?:this|the|your) (?:app|application|tool|assistant|agent)\b|\byou\b|\byour\b", text))
    if (re.search(r"\bservices?\b", text)
            and re.search(r"\b(?:known|supported|support|available|catalog|list|show|which|what|names)\b", text)
            and not re.search(r"\bdepend(?:s|ents|encies)?\b|\b(?:health|freeze|incidents?)\b", text)):
        return "services"
    if not decision and any(re.search(r"(?<![a-z0-9-])" + re.escape(name) + r"(?![a-z0-9-])", text) for name in services):
        return None
    if re.search(r"\b(?:classifier|adversar\w*|abuse)\b|\bsecurity check\b|\bprompt injection\b", text) and (app or re.match(r"\s*(?:what|how|why|does|can)\b", text)):
        return "security"
    if re.search(r"\blocal evidence\b|\bgroq\b|\breview modes?\b", text) or (app and re.search(r"\b(?:llm|model)\b", text)):
        return "modes"
    if re.search(r"\bagent trace\b|\btrace history\b|\b(?:earlier|previous|trace) turns?\b|\badmin(?: panel| tab)?\b", text):
        return "trace"
    if (app or re.match(r"\s*(?:does|do|can|how|what)\b", text)) and re.search(r"\b(?:memory|preferences?|remember)\b|\b(?:save|restore)\b.*\b(?:chat|conversations?)\b|\b(?:chat|conversation) history\b", text):
        if re.search(r"\b(?:how|commands?|syntax)\b", text) and re.search(r"\b(?:save|store|remember|forget|remove)\b", text):
            return "preference_commands"
        return "memory"
    if app and re.search(r"\blimitations?\b|\b(?:cannot|can't|not do|approve|authorize|merge|deploy|block)\b", text):
        return "limits"
    if re.search(r"\bmcp\b|\blanggraph\b|\bwhat tools\b|\btool calling\b", text):
        return "tools"
    if (re.search(r"\b(?:get|getting) started\b|\bwhat (?:should|can) i ask\b|\bexample (?:questions|requests)\b", text)
            or (app and re.search(r"\bhow (?:do i |to )?use\b", text))
            or re.fullmatch(r"\s*how (?:do i |to )?use (?:this|it)[?!. ]*", text)):
        return "examples"
    if (decision and decision.get("topic") == "capabilities") or (app and re.search(r"\b(?:features?|capabilit\w*|functions?)\b", text)):
        return "capabilities"
    if decision or (app and re.search(r"\b(?:what|how|why|does|can|is|tell|explain|describe|about|help|purpose|benefit)\b", text)) or re.fullmatch(r"\s*(?:hi|hello|hey|help(?: me)?)[!?. ]*", text):
        return "overview"
    return None


def capability_lines(copy):
    return [line for line in copy["help_capabilities"].splitlines() if line.strip()]


def help_answer(topic, copy, services, decision=None):
    if topic == "capabilities":
        lines = capability_lines(copy)
        count = decision.get("count", len(lines)) if decision else len(lines)
        return "\n".join(f"{i}. {line}" for i, line in enumerate(lines[:count], 1))
    if topic == "services":
        return copy["help_services"].format(services="\n".join("- " + name for name in sorted(services)))
    if topic in {"examples", "preference_commands"}:
        service = "checkout-service" if "checkout-service" in services else next(iter(sorted(services)), "a known service")
        return copy["help_" + topic].format(service=service)
    return copy["help_" + topic]
