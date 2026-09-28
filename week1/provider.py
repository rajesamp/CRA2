"""Week 1 prompt addition using CRA2's existing protected Groq request path.

No process-global prompt is changed. Week 1 makes one SDK attempt per assessment;
it does not claim a cache hit or deterministic fresh model wording.
"""

import json
from pathlib import Path

from cra2 import config, system2

PROMPT = (
    system2.PROMPT
    + "\n\n"
    + Path(__file__).with_name("prompt.md").read_text(encoding="utf-8")
)


def assess(payload, _weights):
    settings = {
        "model": config.MODEL,
        "temperature": config.TEMPERATURE,
        "seed": config.SEED,
        "max_tokens": config.MAX_TOKENS,
        "reasoning": config.REASONING,
        "timeout": config.TIMEOUT_S,
        "prompt": PROMPT,
        "schema": system2.SCHEMA,
        "provider_schema": system2._provider_schema(system2.SCHEMA),
    }
    system2._reject_credentials([payload, settings], ())
    sdk = system2._protected_client()
    credentials = (getattr(sdk, "api_key", None),)
    system2._reject_credentials([payload, settings], credentials)
    result = system2._request(
        json.dumps(payload, sort_keys=True, allow_nan=False), settings, sdk, credentials
    )
    result["out"]["comments"] = [
        comment
        for comment in result["out"]["comments"]
        if comment["text"].rstrip().endswith("?")
    ]
    result.update(cache_hit=False, request_attempted=True)
    return result
