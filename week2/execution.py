"""Request-local, bounded action coordinator; never model-selected execution.

Only this coordinator commits evidence and state. Cancelled synchronous workers
may finish their read-only work, but cannot publish late results or start actions.
"""

import math
import json
import os
from copy import deepcopy
from dataclasses import dataclass
from functools import partial
from threading import Event
from time import monotonic, perf_counter

import anyio
from jsonschema import Draft202012Validator

from cra2 import system2

from week2.compaction import initial_state, reduce_state
from week2.context_builder import build_context, content_digest, context_json
from week2.contracts import ContractError, NAME, NAMES, obj, semantic_tool_evidence
from week2.instrumentation import _emit
from week2.semantic_state import EVIDENCE_IDENTIFIER, IDENTIFIER, digest, serialize_state


@dataclass(frozen=True)
class ExecutionOptions:
    max_steps: int = 8
    deadline_seconds: float = 30.0
    max_context_bytes: int = 32768
    max_total_context_bytes: int = 131072
    threshold_bytes: int = 8192
    max_output_tokens: int = 1024

    def validate(self):
        for value, lower, upper in (
            (self.max_steps, 1, 32), (self.max_context_bytes, 1, 65536),
            (self.max_total_context_bytes, 1, 1048576), (self.threshold_bytes, 1, 65536),
            (self.max_output_tokens, 1, 4096),
        ):
            if type(value) is not int or not lower <= value <= upper:
                raise ContractError("invalid_execution_options")
        if (type(self.deadline_seconds) not in (int, float)
                or not math.isfinite(self.deadline_seconds) or not 0 < self.deadline_seconds <= 120):
            raise ContractError("invalid_execution_options")
        return self


def selected_mode(explicit=None):
    """Absent setting preserves legacy full behavior; explicit full is a control."""
    mode = explicit if explicit is not None else os.environ.get("CRA2_CONTEXT_MODE")
    if mode is not None and (not isinstance(mode, str) or mode not in {"full", "threshold", "sac"}):
        raise ContractError("invalid_context_mode")
    return mode


def retrieval_records(hits, service):
    """Preserve exact corpus identity, including global documents and # labels."""
    schema = obj({
        "chunk_id": EVIDENCE_IDENTIFIER, "doc_id": IDENTIFIER,
        "title": {"type": "string", "minLength": 1, "maxLength": 300},
        "source": {"type": "string", "minLength": 1, "maxLength": 500},
        "kind": {"enum": ["incident", "postmortem", "runbook", "policy"]},
        "service": {"anyOf": [NAME, {"type": "null"}]},
        "source_dataset": {"type": "string", "minLength": 1, "maxLength": 100},
        "text": {"type": "string", "minLength": 1, "maxLength": 16000},
        "score": {"type": "number", "minimum": -1, "maximum": 1},
    })
    context_json(hits)
    if not isinstance(hits, list) or len(hits) > 3:
        raise ContractError("invalid_retrieval_evidence")
    records, store = [], {}
    for hit in hits:
        if (not Draft202012Validator(schema).is_valid(hit)
                or hit["service"] not in (None, service)
                or hit["chunk_id"] in store):
            raise ContractError("invalid_retrieval_evidence")
        records.append({"id": hit["chunk_id"], "service": service, "origin": "retrieve",
            "kind": "historical", "source_service": hit["service"],
            "source_id": hit["source"], "content_digest": content_digest(hit)})
        store[hit["chunk_id"]] = deepcopy(hit)
    return records, store


def projected_review(result, payload):
    """Recheck exactly the sent allow-list and copy only typed public metadata."""
    try:
        context_json(result)
        tokens = result["tokens"]
        if (tokens is not None and (not isinstance(tokens, list) or len(tokens) != 2
                                   or any(type(n) is not int or n < 0 for n in tokens))):
            raise ValueError
        if type(result["cache_hit"]) is not bool:
            raise ValueError
        attempted = result.get("request_attempted", not result["cache_hit"])
        if type(attempted) is not bool:
            raise ValueError
        safe = {"tokens": deepcopy(tokens), "cache_hit": result["cache_hit"],
                "request_attempted": attempted}
        for key in ("model", "fingerprint"):
            value = result.get(key)
            if value is not None and (not isinstance(value, str) or len(value) > 200):
                raise ValueError
            safe[key] = value
        elapsed = result.get("groq_ms")
        if elapsed is not None and (type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0):
            raise ValueError
        safe["groq_ms"] = elapsed
        comments = result["out"]["comments"]
        if not isinstance(comments, list) or len(comments) > 3:
            raise ValueError
        schema = system2.SCHEMA["properties"]["comments"]["items"]
        allowed, accepted = set(payload["evidence_keys"]), []
        historical = {hit["chunk_id"] for hit in payload["incidents"] + payload["documents"]}
        for comment in comments:
            if not isinstance(comment, dict):
                raise ValueError
            projected = {key: comment[key] for key in ("tag", "severity", "text", "evidence")}
            if not Draft202012Validator(schema).is_valid(projected):
                raise ValueError
            if (projected["text"].rstrip().endswith("?")
                    and set(projected["evidence"]) & historical
                    and system2._comment_allowed(projected, allowed)):
                accepted.append(deepcopy(projected))
        safe["out"] = {"comments": accepted}
        return safe
    except (ValueError, TypeError, KeyError, RecursionError):
        raise ContractError("invalid_execution_review") from None


class ActionExecution:
    def __init__(self, objective, service, policy, actions, *, mode, options=None,
                 cancel_event=None, observer=None):
        self.options = (options or ExecutionOptions()).validate()
        if mode not in {"full", "threshold", "sac"}:
            raise ContractError("invalid_context_mode")
        if cancel_event is not None and not isinstance(cancel_event, Event):
            raise ContractError("invalid_execution_options")
        self.mode, self.cancel_event, self.observer = mode, cancel_event, observer
        self.deadline = monotonic() + self.options.deadline_seconds
        self.policy, self.evidence_store = deepcopy(policy), {}
        self.authority = {
            "change_id": "change-" + digest([objective, service, policy])[:24],
            "objective": objective, "service": service,
            "policy_refs": sorted(set(policy["sources"].values())), "policy_digest": digest(policy),
            "evidence": [], "questions": [],
            "action_plan": [{"id": f"step-{index + 1}", "action": action}
                            for index, action in enumerate(actions)], "action_results": [],
        }
        self.state = initial_state(self.authority)
        self.action_count = self.input_bytes = self.peak_context_bytes = self.compactions = 0
        self.reduction_ms = 0.0
        self.review_started = Event()
        self.stopped = Event()
        self.status = "running"

    def check(self):
        if self.stopped.is_set():
            raise ContractError("execution_stopped")
        if self.cancel_event is not None and self.cancel_event.is_set():
            raise ContractError("execution_cancelled")
        if monotonic() >= self.deadline:
            raise ContractError("execution_deadline")

    def before_request(self):
        self.check()
        return max(.000001, self.deadline - monotonic())

    async def _bounded(self, operation):
        self.check()
        cancelled = False
        try:
            with anyio.fail_after(max(0, self.deadline - monotonic())):
                async with anyio.create_task_group() as group:
                    async def watch_cancel():
                        nonlocal cancelled
                        while True:
                            if self.cancel_event is not None and self.cancel_event.is_set():
                                cancelled = True
                                group.cancel_scope.cancel()
                                return
                            await anyio.sleep(.01)
                    if self.cancel_event is not None:
                        group.start_soon(watch_cancel)
                    result = await operation()
                    group.cancel_scope.cancel()
            if cancelled:
                raise ContractError("execution_cancelled")
            self.check()
            return result
        except TimeoutError:
            self.stopped.set()
            raise ContractError("execution_deadline") from None
        except BaseException:
            # An abandoned worker must never dispatch a *new* model call after
            # the coordinator has stopped. Already-dispatched work may finish.
            self.stopped.set()
            raise

    def charge(self, payload, *, replace_bytes=0, provider_prompt=None):
        context_json(payload)
        size = (len(context_json(payload).encode("utf-8")) if provider_prompt is None else
                len(json.dumps(payload, sort_keys=True, allow_nan=False).encode("utf-8"))
                + len(provider_prompt.encode("utf-8")))
        if (size > self.options.max_context_bytes
                or self.input_bytes - replace_bytes + size > self.options.max_total_context_bytes):
            raise ContractError("context_budget_exceeded")
        self.input_bytes += size - replace_bytes
        self.peak_context_bytes = max(self.peak_context_bytes, size)
        return size

    async def invoke(self, action, operation):
        self.check()
        if self.action_count >= self.options.max_steps:
            raise ContractError("execution_step_budget")
        if self.state["next_action"] != action:
            raise ContractError("invalid_execution_action")
        context = build_context(self.state, self.authority, evidence_store=self.evidence_store,
            policy=self.policy, mode=self.mode, threshold_bytes=self.options.threshold_bytes,
            max_bytes=self.options.max_context_bytes)
        self.compactions = context["compaction_count"]
        previous_bytes = self.input_bytes
        charged = self.charge(context)
        self.action_count += 1
        started = perf_counter()
        failed = True
        try:
            result = await self._bounded(lambda: operation(deepcopy(context), charged))
            failed = False
            return result
        finally:
            if self.observer is not None:
                _emit(self.observer, {"kind": "execution_action", "action": action,
                    "context_mode": self.mode, "context_bytes": self.input_bytes - previous_bytes,
                    "elapsed_ms": (perf_counter() - started) * 1000,
                    "status": "failed" if failed else "completed"})

    def commit(self, action, records=(), sources=None, *, evidence_ids=None, questions=()):
        self.check()
        candidate = deepcopy(self.authority)
        existing = {record["id"]: record for record in candidate["evidence"]}
        for record in records:
            if record["id"] in existing and existing[record["id"]] != record:
                raise ContractError("evidence_conflict")
            if record["id"] not in existing:
                candidate["evidence"].append(deepcopy(record))
        count = len(candidate["action_results"])
        candidate["questions"].extend(deepcopy(questions))
        event = dict(candidate["action_plan"][count], service=candidate["service"], status="ok",
            evidence_ids=sorted(evidence_ids if evidence_ids is not None else [r["id"] for r in records]),
            unresolved_question_ids=sorted(row["id"] for row in questions))
        if event["action"] != action:
            raise ContractError("invalid_execution_action")
        candidate["action_results"].append(event)
        started = perf_counter()
        state = reduce_state(self.state, event, candidate)
        self.reduction_ms += (perf_counter() - started) * 1000
        self.authority, self.state = candidate, state
        self.evidence_store.update(deepcopy(sources or {}))
        if self.mode == "sac":
            self.compactions = len(state["completed_action_ids"])
        elif self.mode == "threshold":
            history, self.compactions = [], 0
            for observation in candidate["action_results"]:
                history.append(observation)
                if len(context_json(history).encode("utf-8")) > self.options.threshold_bytes:
                    history = []
                    self.compactions += 1

    def summary(self, status=None):
        return {"mode": self.mode, "status": status or self.status,
            "action_count": self.action_count, "completed_actions": len(self.state["completed_action_ids"]),
            "model_action_count": int(self.review_started.is_set()),
            "state_bytes": len(serialize_state(self.state, self.authority).encode("utf-8")),
            "input_context_bytes": self.input_bytes, "peak_context_bytes": self.peak_context_bytes,
            "compaction_count": self.compactions, "reduction_ms": self.reduction_ms,
            "context_tokens": None, "max_output_tokens": self.options.max_output_tokens}

    async def collect(self, state, retrieve, run_tools, index_path):
        """Execute the selected read-only plan and retain original guarded records."""
        prepared = deepcopy(state)
        if self.state["next_action"] == "retrieve":
            async def retrieval(context, _charged):
                return await anyio.to_thread.run_sync(partial(retrieve,
                    context["objective"], index_path, limit=3, service=context["service"]),
                    abandon_on_cancel=True)
            hits = await self.invoke("retrieve", retrieval)
            records, store = retrieval_records(hits, self.authority["service"])
            self.commit("retrieve", records, store)
            prepared["hits"] = deepcopy(hits)
        outputs, events = {}, []
        for name, arguments in state["calls"]:
            async def tool_action(_context, _charged):
                return await run_tools([(name, deepcopy(arguments))])
            bundle = await self.invoke(name, tool_action)
            if (not isinstance(bundle, dict) or bundle.get("status") != "ok"
                    or set(bundle.get("outputs", {})) != {name}):
                raise ContractError("execution_tool_failed")
            result = bundle["outputs"][name]
            records = semantic_tool_evidence(name, self.authority["service"], result)
            self.commit(name, records, {record["id"]: result for record in records})
            outputs[name] = deepcopy(result)
            # Rebuild events from validated outputs; untrusted runner events are
            # not an alternate channel into trace, model context or audit data.
            events.append({"event": "tool_result", "tool": name,
                           "input": deepcopy(arguments), "output": deepcopy(result)})
        prepared["tools"] = {"status": "ok", "outputs": outputs, "events": events}
        return prepared

    def review_payload(self, payload, context):
        """Resolve evidence once; history contains references, not duplicated text."""
        hits = [row["content"] for row in context["evidence"].values() if row["kind"] == "historical"]
        outputs = {}
        for row in context["evidence"].values():
            if row["kind"] == "synthetic_snapshot":
                raw = row["content"]
                name = NAMES[0] if "health" in raw else NAMES[1]
                outputs[name] = raw
        fresh = {"change": {"service": context["service"], "summary": context["objective"]},
            "incidents": [hit for hit in hits if hit["kind"] in {"incident", "postmortem"}],
            "documents": [hit for hit in hits if hit["kind"] not in {"incident", "postmortem"}],
            "tool_results": outputs, "settings": context["policy"],
            "settings_conflicts": context["policy"]["conflicts"],
            "evidence_keys": sorted(set(context["evidence"]) | set(self.authority["policy_refs"])),
            "source_scope": payload["source_scope"], "system1_signals": [],
            "execution_context": {key: value for key, value in context.items() if key not in {"evidence", "policy"}},
        }
        context_json(fresh)
        return deepcopy(fresh)
