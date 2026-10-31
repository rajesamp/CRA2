"""Conservative mechanism coverage check, not a semantic entailment model."""
import re
from week1.routing import active_request

APPROVAL = re.compile(r"\b(?:approve|authorize|green[ -]?light|sign[ -]?off|give (?:me |us )?(?:the )?go[ -]?ahead)\b", re.I)
OPERATIONS = re.compile(r"(?:^|[.!?]\s*|\band\s+)(?:(?:please|just|then)\s+)*(?:(?:can|could|will|would) you |i (?:want|need) you to )?(?:merge|deploy|block)\b",re.I)


def approval_request(question):
    text=active_request(question)
    return bool(APPROVAL.search(text) or OPERATIONS.search(text))


def advisory_question(question):
    return re.sub(r"\b(?:approve|authorize|green[ -]?light|sign[ -]?off|give (?:me |us )?(?:the )?go[ -]?ahead|merge|deploy|block)\b",'review',question,flags=re.I)

MECHANISMS = {"timeout": r"\b(?:timeouts?|timed?\s+out)\b",
              "retry": r"\b(?:retr(?:y|ies|ied)|retrying)\b"}


def coverage(question, hits):
    requested = [name for name, pattern in MECHANISMS.items() if re.search(pattern, question, re.I)]
    supported = [name for name in requested if any(
        re.search(MECHANISMS[name], h.get("text", ""), re.I)
        for h in hits if h.get("kind") in {"incident", "postmortem", "runbook"})]
    return {"status": "unsupported" if set(requested)-set(supported) else "not_disproven",
            "method": "bounded_lexical_mechanism_coverage_v1", "requested": requested,
            "covered": supported, "passages_examined": len(hits)}
