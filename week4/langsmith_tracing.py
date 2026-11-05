"""Opt-in, bounded LangSmith exports of reviewed execution facts, never raw state.

Automatic LangGraph/NeMo tracing stays disabled. One background worker sends a
completed, projected run tree; observability failures never change an answer.
"""

from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
import math
import os
from queue import Full, Queue
import re
from threading import Condition, Thread
from urllib.parse import urlparse
from uuid import UUID, uuid4

from cra2.advisor import CATALOG
from cra2.secrets import reject_credentials
from week2.contracts import NAMES, validate_result
from week4.telemetry import STAGES

ENDPOINTS = {
    "https://api.smith.langchain.com": "https://smith.langchain.com",
    "https://eu.api.smith.langchain.com": "https://eu.smith.langchain.com",
}
KEY_NAMES = ("LANGSMITH_API_KEY", "LANGCHAIN_API_KEY")
MAX_RUNS, MAX_BYTES = 48, 65536


def credentials():
    return tuple(os.environ[k] for k in KEY_NAMES if os.environ.get(k))


@dataclass(frozen=True)
class Settings:
    api_key: str = field(repr=False)
    endpoint: str = "https://api.smith.langchain.com"
    project: str | None = "CRA2"
    workspace: str | None = field(default=None, repr=False)
    agent_id: str | None = None
    environment: str | None = None

    @classmethod
    def read(cls):
        if os.getenv("CRA2_LANGSMITH_ENABLED", "").lower() != "true":
            return None
        key = os.getenv("LANGSMITH_API_KEY", "")
        if not key:
            return None
        endpoint = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com").rstrip("/")
        if endpoint not in ENDPOINTS or len(key) > 512 or any(c.isspace() for c in key):
            raise ValueError("invalid_tracing_configuration")
        agent, environment = os.getenv("LANGSMITH_AGENT_ID"), os.getenv("LANGSMITH_AGENT_ENVIRONMENT")
        project = os.getenv("LANGSMITH_PROJECT")
        if agent or environment:
            from langsmith.address import agent_address
            agent_address(agent, environment)
            if project:
                raise ValueError("conflicting_tracing_destination")
        else:
            project = project or "CRA2"
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _.-]{0,79}", project):
                raise ValueError("invalid_tracing_project")
        workspace = os.getenv("LANGSMITH_WORKSPACE_ID") or None
        if workspace:
            workspace = str(UUID(workspace))
        return cls(key, endpoint, project, workspace, agent, environment)


def safe_url(url):
    if not isinstance(url, str) or len(url) > 2048:
        return None
    try:
        parsed = urlparse(url)
        allowed = (parsed.scheme == "https" and parsed.hostname in {"smith.langchain.com", "eu.smith.langchain.com"}
                   and not parsed.username and not parsed.password and parsed.port in (None, 443)
                   and not any(c in url for c in "\r\n<>\"'()\\"))
    except ValueError:
        return None
    if not allowed:
        return None
    return url


def _number(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def _word(value):
    return value if isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9_:-]{0,79}", value) else "unknown"


def _memory(trace):
    memory = trace.get("memory", {})
    effective = memory.get("effective_policy", {}).get("effective", {})
    result = {"status": _word(memory.get("status"))}
    for key in ("high_risk", "freeze_window_active"):
        if type(effective.get(key)) is bool:
            result[key] = effective[key]
    return result


def _cache(trace):
    return [{"layer": e["layer"], "outcome": e["outcome"],
             **{k: e[k] for k in ("age_ms", "duration_ms", "ttl_seconds") if _number(e.get(k)) is not None},
             **({"tool": e["tool"]} if e.get("tool") in NAMES else {})}
            for e in trace.get("cache", [])[:12]
            if e.get("layer") in {"query_embedding", "retrieval", "tool"} and e.get("outcome") in {"hit", "miss"}]


def _evidence(trace):
    return [{"chunk_id": e["chunk_id"], "similarity": e.get("similarity")}
            for e in trace.get("retrieved", [])[:3]
            if isinstance(e.get("chunk_id"), str) and re.fullmatch(r"[A-Za-z0-9_:#.-]{1,160}", e["chunk_id"])
            and type(e.get("similarity")) in (int, float) and math.isfinite(e["similarity"])]


def _time(value):
    stamp = datetime.fromisoformat(value)
    if stamp.utcoffset() is None:
        raise ValueError("invalid_span_time")
    return stamp


def build_runs(trace, settings):
    """Allow-list projection: no questions, history, text, notes, paths or SDK data."""
    root_id = UUID(trace["request_id"])
    thread_id = str(UUID(trace["session_id"]))
    start, end = _time(trace["started_at"]), _time(trace["ended_at"])
    if end < start:
        raise ValueError("invalid_span_time")
    mode = trace.get("review_mode")
    if mode not in {"Local evidence only", "Groq assessment"}:
        raise ValueError("invalid_review_mode")
    turn = trace.get("turn")
    if type(turn) is not int or not 1 <= turn <= 10000:
        raise ValueError("invalid_turn")
    transport = trace.get("transport")
    if transport != "browser":
        raise ValueError("transport_not_enabled")
    metadata = {"thread_id": thread_id, "request_id": str(root_id), "turn": turn,
                "review_mode": mode, "transport": transport, "content_policy": "execution-facts-only"}
    cache = _cache(trace)
    summary = {"status": _word(trace.get("status")), "memory": _memory(trace),
               "cache": cache, "evidence": _evidence(trace),
               "provider_attempted": bool(trace.get("request_attempted")),
               "provider_used": bool(trace.get("provider_used"))}
    risk = trace.get("assessment", {}).get("risk_level")
    if risk in {"low", "medium", "high"}:
        summary["risk_level"] = risk
    if trace.get("support", {}).get("status") in {"supported", "unsupported"}:
        summary["evidence_support"] = trace["support"]["status"]
    root_order = start.strftime("%Y%m%dT%H%M%S%fZ") + str(root_id)
    destination = {"session_name": settings.project} if settings.project else {}
    if settings.agent_id:
        from langsmith.address import agent_address
        destination = {"address": agent_address(settings.agent_id, settings.environment)}

    def run(name, kind, began, finished, outputs, parent=None, inputs=None, error=None):
        identifier = root_id if parent is None else uuid4()
        dotted = root_order if parent is None else parent["dotted_order"] + "." + began.strftime("%Y%m%dT%H%M%S%fZ") + str(identifier)
        return {"id": str(identifier), "trace_id": str(root_id), "dotted_order": dotted,
                "name": name, "run_type": kind, "start_time": began.isoformat(), "end_time": finished.isoformat(),
                "inputs": inputs or {}, "outputs": outputs, "extra": {"metadata": dict(metadata)},
                **destination, **({"parent_run_id": parent["id"]} if parent else {}),
                **({"error": error} if error else {})}

    root = run(f"CRA2 · Turn #{turn} · {mode}", "chain", start, end, summary,
               inputs={"review_mode": mode, "turn": turn, "content": "excluded"})
    runs, stages = [root], {}
    for span in trace.get("spans", [])[:24]:
        stage = span.get("stage")
        if stage not in STAGES or "started_at" not in span or "ended_at" not in span:
            continue
        began, finished = _time(span["started_at"]), _time(span["ended_at"])
        if not start <= began <= finished <= end:
            raise ValueError("invalid_span_time")
        output = {"outcome": _word(span.get("outcome"))}
        if stage in {"memory_read", "memory_write"}:
            output["memory"] = summary["memory"]
        if stage in {"retrieve", "legacy"}:
            output.update(evidence=summary["evidence"], cache=[e for e in cache if e["layer"] != "tool"])
        if stage == "tools":
            output["cache"] = [e for e in cache if e["layer"] == "tool"]
        kind = "retriever" if stage == "retrieve" else "llm" if (stage == "reviewer"
                and span.get("outcome") == "invoked_provider_adapter" and trace.get("request_attempted")) else "chain"
        child = run(stage, kind, began, finished, output, root,
                    error="execution_failed" if span.get("outcome") == "error" else None)
        stages[stage] = child
        runs.append(child)
    reviewer = stages.get("reviewer")
    if reviewer and "compose" in stages:
        parent = stages["compose"]
        reviewer["parent_run_id"] = parent["id"]
        reviewer["dotted_order"] = parent["dotted_order"] + "." + reviewer["dotted_order"].split(".")[-1]
        tokens = trace.get("tokens")
        if isinstance(tokens, list) and len(tokens) == 2 and all(type(t) is int and t >= 0 for t in tokens):
            reviewer["outputs"]["usage_metadata"] = {"input_tokens": tokens[0], "output_tokens": tokens[1], "total_tokens": sum(tokens)}
    for event in trace.get("events", [])[:8]:
        name = event.get("tool")
        if event.get("event") != "tool_result" or name not in NAMES:
            continue
        arguments = event.get("input", {})
        service = arguments.get("service_name")
        if service not in CATALOG or set(arguments) != {"service_name"}:
            raise ValueError("invalid_tool_projection")
        result = validate_result(name, service, event["output"])
        if "started_at" not in event or "ended_at" not in event:
            continue
        began, finished = _time(event["started_at"]), _time(event["ended_at"])
        if not start <= began <= finished <= end:
            raise ValueError("invalid_span_time")
        runs.append(run(name, "tool", began, finished, result, stages.get("tools", root), arguments))
    for event in trace.get("rails", [])[:3]:
        if event.get("stage") not in {"input", "context", "output"} or "started_at" not in event:
            continue
        began, finished = _time(event["started_at"]), _time(event["ended_at"])
        if not start <= began <= finished <= end:
            raise ValueError("invalid_span_time")
        outputs = {"outcome": _word(event.get("outcome")), "engine": "nemoguardrails"}
        parent = stages.get({"input": "classify", "context": "retrieve", "output": "output_guard"}[event["stage"]], root)
        runs.append(run("guardrail_" + event["stage"], "chain", began, finished, outputs, parent))
    reject_credentials(runs, additional=credentials())
    if len(runs) > MAX_RUNS or len(json.dumps(runs, allow_nan=False).encode()) > MAX_BYTES:
        raise ValueError("trace_too_large")
    return runs


class CheckedClient:
    """The SDK can swallow ingestion errors; require its error callback to be clear."""
    def __init__(self, client, failures):
        self.client, self.failures = client, failures

    def batch_ingest_runs(self, **kwargs):
        self.failures.clear()
        self.client.batch_ingest_runs(**kwargs)
        if self.failures:
            raise ValueError("trace_ingestion_failed")

    def __getattr__(self, name):
        return getattr(self.client, name)


def make_client(settings):
    from langsmith import Client
    from urllib3.util.retry import Retry
    for name in ["langsmith", *logging.Logger.manager.loggerDict]:
        if name == "langsmith" or name.startswith("langsmith."):
            logging.getLogger(name).disabled = True
    failures = []
    client = Client(api_key=settings.api_key, api_url=settings.endpoint,
                  web_url=ENDPOINTS[settings.endpoint], workspace_id=settings.workspace,
                  retry_config=Retry(total=0), timeout_ms=(3000, 15000),
                  auto_batch_tracing=False, omit_traced_runtime_info=True, tracing_sampling_rate=1,
                  tracing_error_callback=lambda _: failures.append(True))
    return CheckedClient(client, failures)


class LangSmithExporter:
    def __init__(self, *, settings_reader=Settings.read, client_factory=make_client, capacity=16):
        self.settings_reader, self.client_factory = settings_reader, client_factory
        self.queue = Queue(maxsize=capacity)
        self.condition, self.records, self.pending = Condition(), OrderedDict(), 0
        self.worker = None

    def _save(self, key, value):
        with self.condition:
            self.records[key] = value
            self.records.move_to_end(key)
            while len(self.records) > 512:
                self.records.popitem(last=False)

    def status(self, trace):
        with self.condition:
            if trace.get("request_id") in self.records:
                return dict(self.records[trace["request_id"]])
            status = trace.get("langsmith", {"status": "not_configured"})
            return {"status": "expired"} if status.get("status") == "queued" else dict(status)

    def submit(self, trace):
        if trace.get("transport") != "browser":
            return {"status": "not_enabled_for_transport"}
        try:
            settings = self.settings_reader()
            if settings is None:
                return {"status": "not_configured"}
            runs = build_runs(trace, settings)
            key = trace["request_id"]
            with self.condition:
                if self.worker is None:
                    self.worker = Thread(target=self._work, name="cra2-trace-export", daemon=True)
                    self.worker.start()
                self.queue.put_nowait((key, settings, runs))
                self.pending += 1
                self._save(key, {"status": "queued", "run_id": runs[0]["id"]})
            return {"status": "queued", "run_id": runs[0]["id"]}
        except Full:
            return {"status": "queue_full"}
        except Exception:
            return {"status": "unavailable"}

    def _work(self):
        while True:
            key, settings, runs = self.queue.get()
            client = None
            try:
                client = self.client_factory(settings)
                # The SDK normalizes IDs/timestamps in-place. Keep our reviewed
                # tree unchanged for URL resolution and serializable UI status.
                client.batch_ingest_runs(create=deepcopy(runs))
                submitted = {"status": "submitted", "run_id": runs[0]["id"]}
                self._save(key, dict(submitted, status="resolving_link"))
                # Resolve through the SDK; never manufacture a public/share link.
                try:
                    from langsmith.run_trees import RunTree
                    root = runs[0]
                    tree = RunTree(id=UUID(root["id"]), name=root["name"], start_time=_time(root["start_time"]),
                                   ls_client=client, project_name=settings.project, address=root.get("address"))
                    lookups = (tree.get_url, lambda: client.get_run_url(
                        run=tree, project_name=settings.project, address=root.get("address")))
                    for lookup in lookups:
                        try:
                            url = safe_url(lookup())
                            if url:
                                reject_credentials(url, additional=(settings.api_key,))
                                submitted["url"] = url
                                break
                        except Exception:
                            continue
                except Exception:
                    pass  # A tracing-only key can ingest without URL lookup permission.
                self._save(key, submitted)
            except Exception:
                self._save(key, {"status": "unavailable"})
            finally:
                if client is not None:
                    try:
                        client.close(timeout=1)
                    except Exception:
                        pass
                with self.condition:
                    self.pending -= 1
                    self.condition.notify_all()
                self.queue.task_done()

    def flush(self, timeout=10):
        with self.condition:
            return self.condition.wait_for(lambda: self.pending == 0, timeout)


EXPORTER = LangSmithExporter()
