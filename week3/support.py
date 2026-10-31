"""Conservative mechanism coverage check, not a semantic entailment model."""
import re

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
