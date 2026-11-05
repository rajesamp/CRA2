"""Opt-in, in-process measurements; never retain graph state or provider content.

Elapsed times are nested wall times, not additive. Observer failures cannot change
the advisory result. Callers own observer storage and its retention policy.
"""

from functools import wraps
from inspect import iscoroutinefunction
from time import perf_counter


def _emit(observer, event):
    try:
        observer(event)
    except Exception:
        # Telemetry is optional and must not change routing/safety behavior.
        pass


def observe_node(name, node, observer):
    if observer is None:
        return node

    def report(start, state, failed):
        event = {"kind": "action", "action": name,
                 "elapsed_ms": (perf_counter() - start) * 1000,
                 "status": "failed" if failed else "completed"}
        if name == "tools":
            event["tool_calls"] = len(state.get("calls", []))
        _emit(observer, event)

    if iscoroutinefunction(node):
        @wraps(node)
        async def asynchronous(state):
            start, failed = perf_counter(), True
            try:
                result = await node(state)
                failed = False
                return result
            finally:
                report(start, state, failed)
        return asynchronous

    @wraps(node)
    def synchronous(state):
        start, failed = perf_counter(), True
        try:
            result = node(state)
            failed = False
            return result
        finally:
            report(start, state, failed)
    return synchronous


def observe_reviewer(reviewer, observer, *, source="injected"):
    if observer is None:
        return reviewer

    @wraps(reviewer)
    def measured(payload, weights):
        start, result, failure = perf_counter(), None, None
        try:
            result = reviewer(payload, weights)
            return result
        except Exception as exc:
            failure = exc
            raise
        finally:
            # Copy only typed numeric usage and booleans; no payloads, answers,
            # exception messages, owner records, model IDs or evidence text.
            metadata = result if isinstance(result, dict) else {}
            tokens = metadata.get("tokens", getattr(failure, "tokens", None))
            valid = (isinstance(tokens, (list, tuple)) and len(tokens) == 2
                     and all(type(n) is int and n >= 0 for n in tokens))
            attempted = metadata.get("request_attempted",
                                     getattr(failure, "request_attempted", None))
            cached = metadata.get("cache_hit")
            _emit(observer, {"kind": "provider", "action": "review",
                "source": source, "usage_source": "reviewer_reported",
                "elapsed_ms": (perf_counter() - start) * 1000,
                "status": "failed" if failure is not None else "completed",
                "request_attempted": attempted if type(attempted) is bool else None,
                "cache_hit": cached if type(cached) is bool else None,
                "input_tokens": tokens[0] if valid else None,
                "output_tokens": tokens[1] if valid else None,
                "usage_status": "available" if valid else "missing"})
    return measured
