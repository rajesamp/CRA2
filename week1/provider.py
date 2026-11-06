"""Week 1 prompt addition using CRA2's existing protected Groq request path.

No process-global prompt is changed. Week 1 makes one SDK attempt per assessment;
it does not claim a cache hit or deterministic fresh model wording.
"""

import json
import math
from pathlib import Path

from cra2 import config, system2

PROMPT = (
    system2.PROMPT
    + "\n\n"
    + Path(__file__).with_name("prompt.md").read_text(encoding="utf-8")
)


def assess(payload, _weights, *, timeout=None, max_tokens=None, before_request=None):
    # Trusted host ceilings for bounded action execution. Never extend configured
    # limits; ordinary callers retain the existing request settings unchanged.
    if timeout is not None and (type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0):
        raise ValueError("Invalid provider timeout")
    if max_tokens is not None and (type(max_tokens) is not int or max_tokens <= 0):
        raise ValueError("Invalid provider token limit")
    if before_request is not None and not callable(before_request):
        raise ValueError("Invalid provider dispatch guard")
    settings = {
        "model": config.MODEL,
        "temperature": config.TEMPERATURE,
        "seed": config.SEED,
        "max_tokens": config.MAX_TOKENS if max_tokens is None else min(config.MAX_TOKENS, max_tokens),
        "reasoning": config.REASONING,
        "timeout": config.TIMEOUT_S if timeout is None else min(config.TIMEOUT_S, timeout),
        "prompt": PROMPT,
        "schema": system2.SCHEMA,
        "provider_schema": system2._provider_schema(system2.SCHEMA),
    }
    system2._reject_credentials([payload, settings], ())
    sdk = system2._protected_client()
    credentials = (getattr(sdk, "api_key", None),)
    system2._reject_credentials([payload, settings], credentials)
    result = system2._request(
        json.dumps(payload, sort_keys=True, allow_nan=False), settings, sdk, credentials,
        **({"before_request": before_request} if before_request is not None else {}),
    )
    result["out"]["comments"] = [
        comment
        for comment in result["out"]["comments"]
        if comment["text"].rstrip().endswith("?")
    ]
    result.update(cache_hit=False, request_attempted=True)
    return result
