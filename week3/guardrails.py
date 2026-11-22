"""Real NeMo custom actions, with no configured LLM or embedding requests.

Each request owns its engine and events. Context is checked using an input
rail at the host retrieval boundary; this is not a NeMo-managed RAG pipeline.
Only bounded verdict metadata leaves the engine, never its conversation log.
"""

import json
import logging
import re
import unicodedata
from pathlib import Path
from time import perf_counter

from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.actions import action
from nemoguardrails.rails.llm.options import RailStatus

from cra2.advisor import ADVISORY
from week1.responses import guard
from week2.contracts import checked

CONFIG = Path(__file__).with_name("rails")
INJECTION = re.compile(r"\b(?:ignore|override|disregard)\b.{0,50}\b(?:instructions|system prompt|guardrails)\b", re.I)
APPROVAL = re.compile(
    r"\b(?:i|we)\s+(?:(?:hereby|explicitly|can|will)\s+)?(?:approve|authori[sz]e|green[ -]?light|sign off on)\b"
    r"|\byou have (?:my|our) (?:explicit )?(?:approval|authori[sz]ation|permission|go[ -]?ahead)\b"
    r"|\byou (?:are|have been) (?:approved|authori[sz]ed|cleared) to (?:deploy|release|ship|merge)\b"
    r"|\b(?:this|the) (?:change|deployment|release|rollout) (?:is|has been) (?:approved|authori[sz]ed|cleared)\b"
    r"|\b(?:i|we) (?:give|grant) (?:you )?(?:the |my |our )?(?:approval|permission|green light|go[ -]?ahead)\b"
    r"|\bgo ahead (?:and|to) (?:deploy|release|ship|merge)\b", re.I)
CLEARANCE = re.compile(r"\b(?:approved for (?:deployment|release)|safe to (?:ship|deploy))\b", re.I)
NEGATED_CLEARANCE = re.compile(r"\b(?:not|never|cannot (?:say|confirm)(?: (?:that )?it is)?)\s*$", re.I)


def operational_approval(text):
    """Bounded language check, not a semantic proof. Refusals do not cancel grants.

    Normalize display formatting before matching; allow only immediately negated
    clearance phrases, never a sentence-wide 'not' exemption.
    """
    text = unicodedata.normalize('NFKC', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Cf' and c not in '*_`')
    text = re.sub(r'\s+', ' ', text)
    return bool(APPROVAL.search(text)) or any(
        not NEGATED_CLEARANCE.search(text[:match.start()])
        for match in CLEARANCE.finditer(text))


class RailUnavailable(ValueError):
    """A required check did not produce a verifiable verdict."""


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _strings(item)


def _context_fields(payload):
    checked(payload, "invalid_evidence")
    if not isinstance(payload, list) or not all(
        isinstance(hit, dict) and isinstance(hit.get("text"), str)
        and isinstance(hit.get("chunk_id"), str) and hit["chunk_id"].strip()
        and ("title" not in hit or isinstance(hit["title"], str)) for hit in payload
    ):
        raise RailUnavailable("invalid_evidence")
    original = list(_strings(payload))
    normalized = []
    for value in original:
        value = unicodedata.normalize("NFKC", value)
        visible = "".join(c for c in value if unicodedata.category(c) != "Cf")
        normalized.append(" ".join(visible.split()))
    checked(normalized, "invalid_evidence")
    return original, normalized


def _unavailable_event(stage, started):
    return {"stage": stage, "engine": "nemoguardrails", "version": "0.24.1",
            "executed": False, "outcome": "unavailable", "severity": "M3",
            "code": "rail_unavailable", "duration_ms": round((perf_counter()-started)*1000, 3)}


async def check_context(rails, hits):
    """Require a fresh, consistent context receipt before releasing this batch."""
    start = len(rails.events)
    started = perf_counter()
    try:
        allowed = await rails.check("context", hits)
        receipt, = rails.events[start:]
        if (type(allowed) is not bool or receipt.get("stage") != "context"
                or receipt.get("engine") != "nemoguardrails" or receipt.get("executed") is not True
                or receipt.get("outcome") != ("allow" if allowed else "block")
                or receipt.get("code") != ("contract_valid" if allowed else "untrusted_context")):
            raise RailUnavailable("inconsistent_verdict")
        return allowed
    except Exception:
        rails.events[start:] = [_unavailable_event("context", started)]
        raise RailUnavailable("rail_unavailable") from None


class LocalRails:
    def __init__(self):
        # NeMo diagnostics can contain message text. Export only our own events.
        for name in ["nemoguardrails", *logging.Logger.manager.loggerDict]:
            if name == "nemoguardrails" or name.startswith("nemoguardrails."):
                logging.getLogger(name).disabled = True
        self.engine = LLMRails(RailsConfig.from_path(str(CONFIG)))
        self.events = []

    async def check(self, stage, payload):
        if stage not in {"input", "context", "output"}:
            raise RailUnavailable("invalid_stage")
        verdict = []
        started = perf_counter()

        @action(is_system_action=True)
        async def validate(context):
            code, allowed = "contract_valid", True
            if stage == "input":
                from week2.abuse import prohibited_request
                allowed = not prohibited_request(payload)
                code = "protected_action" if not allowed else code
            elif stage == "context":
                allowed = not any(INJECTION.search(value) for view in fields for value in view)
                code = "untrusted_context" if not allowed else code
            else:
                text, trace = payload["answer"], payload["trace"]
                allowed = not operational_approval(text)
                if trace.get("status") == "assessed":
                    allowed = allowed and bool(trace.get("retrieved")) and text.endswith(ADVISORY)
                code = "unsupported_output" if not allowed else code
            verdict.append((allowed, code))
            return allowed

        # No model-dependent rail is configured. check_async avoids generation.
        role = "assistant" if stage == "output" else "user"
        try:
            if stage == "context":
                fields = _context_fields(payload)
                # The registered local action owns the bounded values. NeMo's
                # message history only needs a trigger for that action.
                raw = "Evaluate selected evidence."
            else:
                guard(payload)
                raw = json.dumps(payload, ensure_ascii=False, allow_nan=False)
            self.engine.register_action(validate, name="cra_validate")
            result = await self.engine.check_async([{"role": role, "content": raw}])
            if len(verdict) != 1 or result.status not in {RailStatus.PASSED, RailStatus.BLOCKED}:
                raise RailUnavailable("missing_verdict")
            allowed, code = verdict[0]
            if allowed != (result.status == RailStatus.PASSED):
                raise RailUnavailable("inconsistent_verdict")
            self.events.append({"stage": stage, "engine": "nemoguardrails", "version": "0.24.1",
                "executed": True, "outcome": "allow" if allowed else "block",
                "severity": "M0" if allowed else "M4" if stage == "input" else "M2",
                "code": code, "duration_ms": round((perf_counter()-started)*1000, 3)})
            # NeMo keeps internal event history for conversational use. This
            # host deliberately does not continue that history between checks.
            self.engine.events_history_cache.clear()
            return allowed
        except Exception:
            self.events.append(_unavailable_event(stage, started))
            raise RailUnavailable("rail_unavailable") from None
