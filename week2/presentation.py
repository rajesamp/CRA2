"""Bounded public change facts and review checks, separate from diagnostics."""

import re
from decimal import Decimal

from cra2.advisor import _inline
from week1.routing import active_request

NUMBER = r"\d{1,6}(?:\.\d{1,3})?"
UNIT = r"milliseconds?|msecs?|ms|seconds?|secs?|s|minutes?|mins?"
TIME_PAIR = re.compile(r"\bfrom\s+(" + NUMBER + r")\s*(" + UNIT
                       + r")\s+to\s+(" + NUMBER + r")\s*(" + UNIT + r")\b")
RETRY_PAIR = re.compile(r"\bfrom\s+(\d{1,6})\s+to\s+(\d{1,6})(?![\d.])\b")
DIAGNOSTIC = re.compile(r"(?:catalog|graph|memory):|:chunk-|\b(?:week[12]|cra2)/|/Users/|/tmp/", re.I)


def _seconds(number, unit):
    scale = Decimal(".001") if unit.startswith("m") and not unit.startswith("min") else (
        Decimal(60) if unit.startswith("min") else Decimal(1))
    return Decimal(number) * scale


def _change_facts(question, copy):
    """Arithmetic describes supplied values; checklists make no incident claims."""
    text = active_request(question)
    fact = ""
    if re.search(r"\btimeouts?\b", text):
        pairs = TIME_PAIR.findall(text)
        if len(pairs) == 1:
            before, before_unit, after, after_unit = pairs[0]
            old, new = _seconds(before, before_unit), _seconds(after, after_unit)
            # Zero may have configuration-specific semantics, such as disabling
            # a timeout. Do not infer those semantics or divide by zero.
            if old > 0 and new > 0 and old != new:
                value = abs(new - old) / old * 100
                if value < Decimal(".1"):
                    percent = "less than 0.1"
                elif Decimal("99.9") < value < 100:
                    percent = "more than 99.9"
                else:
                    percent = format(value, ".1f").rstrip("0").rstrip(".")
                fact = copy["chat_timeout_change"].format(
                    direction="decreases" if new < old else "increases", percent=percent)
        checks = copy["chat_timeout_checks"]
    elif re.search(r"\bretr(?:y|ies)\b", text):
        pairs = RETRY_PAIR.findall(text)
        if len(pairs) == 1:
            before, after = pairs[0]
            fact = copy["chat_retry_change"].format(before=int(before), after=int(after))
        checks = copy["chat_retry_checks"]
    else:
        checks = copy["chat_change_checks"]
    return fact, checks


def review_summary(trace, copy):
    question = trace.get("question", "")
    fact, checks = _change_facts(question if isinstance(question, str) else "", copy)
    if trace["status"] == "assessed":
        questions, words = [], 0
        reviews = trace.get("assessment", {}).get("review_questions", [])
        for comment in reviews if isinstance(reviews, list) else []:
            if not isinstance(comment, dict):
                continue
            text = comment.get("text")
            evidence = comment.get("evidence", [])
            if (not isinstance(text, str) or not text.endswith("?") or len(text) > 240
                    or DIAGNOSTIC.search(text) or any(c in text for c in "\n\r\t")
                    or not isinstance(evidence, list)
                    or any(isinstance(key, str) and key and key in text for key in evidence)
                    or words + len(text.split()) > 30):
                continue
            questions.append(_inline(text))
            words += len(text.split())
            if len(questions) == 2:
                break
        if questions:
            checks = copy["chat_review_checks"].format(checks=" ".join(questions))
    return [part for part in (fact, checks) if part]
