"""Bounded Groq assessment with local validation and a process-local result cache.

Fixed sampling settings reduce variation; they do not guarantee reproducibility
across provider updates. Only a validated cached result is exactly repeatable.
"""

import json
import math
import re
import threading
import unicodedata
from collections import OrderedDict
from functools import cache

import groq

from cra2 import config
from cra2.secrets import configure_sdk_logging, reject_credentials

PROMPT = (config.PKG_DIR / "prompts" / "system_prompt.md").read_text(encoding="utf-8")
SCHEMA = json.loads(
    (config.PKG_DIR / "prompts" / "assessment.schema.json").read_text(encoding="utf-8")
)
_CACHE_LIMIT = 512
_RESULTS: OrderedDict[tuple[str, str], str] = OrderedDict()
_CACHE_LOCK = threading.Lock()
# Conservative checks for common execution/approval claims. This is an output
# hygiene filter, not a proof that arbitrary model prose is factually grounded.
_DECISION = re.compile(
    r"\b(?:approve[ds]?|approval|cleared|authorized|safe|block(?:ed)?|merge[ds]?)\b"
    r"|(?:^|[.!?;]\s*)(?:please\s+)?(?:deploy|ship|roll\s*out)\b"
    r"|\b(?:can|may|should|must|go\s+ahead\s+and)\s+(?:now\s+)?(?:deploy|ship|roll\s*out)\b",
    re.IGNORECASE,
)


class System2Unavailable(ValueError):
    """Expected provider/response failure, with accounting for this assessment."""

    def __init__(
        self,
        message: str,
        *,
        request_attempted: bool = False,
        tokens: list[int] | None = None,
        groq_ms: int | None = None,
    ):
        super().__init__(message)
        self.request_attempted = request_attempted
        self.tokens = tokens
        self.groq_ms = groq_ms


ERRORS = (System2Unavailable,)


@cache
def client() -> groq.Groq:
    # One SDK invocation must never silently become a retry loop.
    configure_sdk_logging()
    return groq.Groq(
        timeout=config.TIMEOUT_S, max_retries=0, base_url="https://api.groq.com"
    )


def _protected_client():
    configure_sdk_logging()
    failure = None
    try:
        sdk = client()
    except groq.GroqError:
        failure = System2Unavailable("Groq client is unavailable")
    if failure is not None:
        # Raise after leaving the handler so the provider exception (which may
        # contain authentication headers) is absent even from __context__.
        raise failure from None
    configure_sdk_logging()
    return sdk


def _reject_credentials(
    value, credentials, *, request_attempted=False, tokens=None, groq_ms=None
):
    failure = None
    try:
        reject_credentials(value, additional=credentials)
    except ValueError:
        failure = System2Unavailable(
            "Configured credentials were found in application data",
            request_attempted=request_attempted,
            tokens=tokens,
            groq_ms=groq_ms,
        )
    if failure is not None:
        raise failure from None


def _validate(value, schema: dict, path: str = "response") -> None:
    """Validate the deliberately small JSON-schema vocabulary in our contract.

    Objects are closed and complete; arrays and strings have explicit bounds.
    Unsupported schema types are programming errors, not provider failures.
    """
    kind = schema["type"]
    if kind == "object":
        if not isinstance(value, dict) or set(value) != set(schema["properties"]):
            raise ValueError(f"{path} must contain exactly its declared fields")
        for name, child in schema["properties"].items():
            _validate(value[name], child, f"{path}.{name}")
    elif kind == "array":
        if not isinstance(value, list):
            raise ValueError(f"{path} must be an array")
        if (
            not schema.get("minItems", 0)
            <= len(value)
            <= schema.get("maxItems", math.inf)
        ):
            raise ValueError(f"{path} has an invalid number of items")
        for child in value:
            _validate(child, schema["items"], f"{path}[]")
        if schema.get("uniqueItems") and len(
            {json.dumps(v, sort_keys=True) for v in value}
        ) != len(value):
            raise ValueError(f"{path} contains duplicate items")
    elif kind == "string":
        if not isinstance(value, str):
            raise ValueError(f"{path} must be a string")
        if (
            not schema.get("minLength", 0)
            <= len(value)
            <= schema.get("maxLength", math.inf)
        ):
            raise ValueError(f"{path} has an invalid length")
        if "enum" in schema and value not in schema["enum"]:
            raise ValueError(f"{path} is not a declared enum value")
    else:
        raise RuntimeError(f"Unsupported assessment schema type: {kind}")


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def _nonfinite(value):
    raise ValueError("Nonfinite JSON number")


def _usage(response) -> tuple[list[int] | None, int | None]:
    usage = getattr(response, "usage", None)
    counts = [
        getattr(usage, name, None) for name in ("prompt_tokens", "completion_tokens")
    ]
    tokens = (
        counts if all(type(count) is int and count >= 0 for count in counts) else None
    )
    duration = getattr(usage, "total_time", None)
    elapsed = None
    if type(duration) in (int, float) and duration >= 0:
        try:
            milliseconds = float(duration) * 1000
            if math.isfinite(milliseconds):
                elapsed = round(milliseconds)
        except OverflowError:
            pass  # Malformed provider timing must not discard a usable assessment.
    return tokens, elapsed


def _comment_allowed(comment: dict, evidence: set[str]) -> bool:
    text = comment["text"]
    return (
        bool(text.strip())
        and set(comment["evidence"]) <= evidence
        and not any(unicodedata.category(char).startswith("C") for char in text)
        and not re.search(r"[<>`\\]|!?\[[^\]]*\]\(|https?://", text, re.IGNORECASE)
        and not _DECISION.search(text)
    )


def _request(payload: str, settings: dict, sdk, credentials) -> dict:
    failure = None
    try:
        response = sdk.chat.completions.create(
            model=settings["model"],
            temperature=settings["temperature"],
            seed=settings["seed"],
            max_completion_tokens=settings["max_tokens"],
            timeout=settings["timeout"],
            **settings["reasoning"],
            messages=[
                {"role": "system", "content": settings["prompt"]},
                {"role": "user", "content": payload},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "assessment",
                    "schema": settings["schema"],
                    "strict": True,
                },
            },
        )
    except (groq.GroqError, ValueError, RecursionError):
        # SDK decoding can raise ValueError for oversized JSON integers, as well
        # as its JSONDecodeError/UnicodeDecodeError subclasses. Keep this catch
        # at the provider boundary so local scoring defects still surface.
        failure = System2Unavailable("Groq request failed", request_attempted=True)
    if failure is not None:
        raise failure from None
    tokens, elapsed = _usage(response)
    model, fingerprint = (
        getattr(response, "model", None),
        getattr(response, "system_fingerprint", None),
    )
    _reject_credentials(
        [model, fingerprint],
        credentials,
        request_attempted=True,
        tokens=tokens,
        groq_ms=elapsed,
    )
    try:
        choices = getattr(response, "choices", None)
        if not isinstance(choices, list) or len(choices) != 1:
            raise ValueError("Expected exactly one completion")
        choice = choices[0]
        if getattr(choice, "finish_reason", "stop") != "stop":
            raise ValueError("Completion was incomplete or refused")
        message = getattr(choice, "message", None)
        content = getattr(message, "content", None)
        reject_credentials(
            [content, getattr(message, "refusal", None)], additional=credentials
        )
        if (
            getattr(message, "refusal", None)
            or not isinstance(content, str)
            or len(content) > 16384
        ):
            raise ValueError("Missing or oversized completion")
        out = json.loads(content, object_pairs_hook=_object, parse_constant=_nonfinite)
        reject_credentials(out, additional=credentials)
        _validate(out, settings["schema"])
        evidence = set(json.loads(payload)["evidence_keys"])
        out["comments"] = [c for c in out["comments"] if _comment_allowed(c, evidence)]
    except (ValueError, TypeError, KeyError, RecursionError):
        failure = System2Unavailable(
            "Invalid Groq assessment",
            request_attempted=True,
            tokens=tokens,
            groq_ms=elapsed,
        )
    if failure is not None:
        raise failure from None
    return {
        "out": out,
        "model": model if isinstance(model, str) else None,
        "fingerprint": fingerprint if isinstance(fingerprint, str) else None,
        "tokens": tokens,
        "groq_ms": elapsed,
    }


def call(payload: str) -> str:
    """Return validated JSON; cache identity includes all request-affecting settings.

    Cache entries contain immutable JSON. Concurrent cache misses may each make
    one request; no lock is held across network I/O. Failed replies are not cached.
    """
    settings = {
        "model": config.MODEL,
        "temperature": config.TEMPERATURE,
        "seed": config.SEED,
        "max_tokens": config.MAX_TOKENS,
        "reasoning": config.REASONING,
        "timeout": config.TIMEOUT_S,
        "prompt": PROMPT,
        "schema": SCHEMA,
    }
    _reject_credentials([payload, settings], ())
    sdk = _protected_client()
    credentials = (getattr(sdk, "api_key", None),)
    _reject_credentials([payload, settings], credentials)
    key = (payload, json.dumps(settings, sort_keys=True, allow_nan=False))
    with _CACHE_LOCK:
        stored = _RESULTS.get(key)
        if stored is not None:
            _RESULTS.move_to_end(key)
    if stored is not None:
        result = json.loads(stored)
        try:
            _reject_credentials(result, credentials)
        except System2Unavailable:
            with _CACHE_LOCK:
                _RESULTS.pop(key, None)
            raise
        result.update(
            tokens=[0, 0], groq_ms=None, cache_hit=True, request_attempted=False
        )
    else:
        result = _request(payload, settings, sdk, credentials)
        with _CACHE_LOCK:
            _RESULTS[key] = json.dumps(result, allow_nan=False)
            _RESULTS.move_to_end(key)
            if len(_RESULTS) > _CACHE_LIMIT:
                _RESULTS.popitem(last=False)
        result.update(cache_hit=False, request_attempted=True)
    return json.dumps(result, allow_nan=False)


def _clear_cache() -> None:
    with _CACHE_LOCK:
        _RESULTS.clear()


call.cache_clear = _clear_cache


def assess(payload: dict, w: dict) -> dict:
    result = json.loads(call(json.dumps(payload, sort_keys=True, allow_nan=False)))
    values = [w["rating_value"][value] for value in result["out"]["ratings"].values()]
    result["score"] = round(
        w["worst_weight"] * max(values)
        + (1 - w["worst_weight"]) * sum(values) / len(values),
        2,
    )
    return result
