"""Real NeMo custom actions, with no configured LLM or embedding requests.

Each request owns its engine and events. Context is checked using an input
rail at the host retrieval boundary; this is not a NeMo-managed RAG pipeline.
Only bounded verdict metadata leaves the engine, never its conversation log.
"""

import json
import logging
import re
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
APPROVAL = re.compile(r"\b(?:i approve|approved for (?:deployment|release)|safe to (?:ship|deploy)|go ahead and deploy)\b", re.I)


class RailUnavailable(ValueError):
    """A required check did not produce a verifiable verdict."""


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
        guard(payload)
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
                checked(payload, "invalid_evidence")
                allowed = isinstance(payload, list) and all(
                    isinstance(h, dict) and isinstance(h.get("text"), str)
                    and isinstance(h.get("chunk_id"), str) and h["chunk_id"]
                    and not INJECTION.search(h["text"]) for h in payload)
                code = "untrusted_context" if not allowed else code
            else:
                text, trace = payload["answer"], payload["trace"]
                allowed = not APPROVAL.search(text)
                if trace.get("status") == "assessed":
                    allowed = allowed and bool(trace.get("retrieved")) and text.endswith(ADVISORY)
                code = "unsupported_output" if not allowed else code
            verdict.append((allowed, code))
            return allowed

        # No model-dependent rail is configured. check_async avoids generation.
        self.engine.register_action(validate, name="cra_validate")
        role = "assistant" if stage == "output" else "user"
        try:
            raw = json.dumps(payload, ensure_ascii=False, allow_nan=False)
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
            self.events.append({"stage": stage, "engine": "nemoguardrails", "version": "0.24.1",
                "executed": False, "outcome": "unavailable", "severity": "M3",
                "code": "rail_unavailable", "duration_ms": round((perf_counter()-started)*1000, 3)})
            raise RailUnavailable("rail_unavailable") from None
