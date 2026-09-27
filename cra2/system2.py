"""System 2: one Groq call that rates five release-engineering risk areas and writes grounded comments.
Temperature 0, a fixed seed, a pinned model and a strict JSON schema keep repeat answers the same."""

import json
from functools import cache, lru_cache

import groq

from cra2 import config

PROMPT = (config.PKG_DIR / "prompts" / "system_prompt.md").read_text()
SCHEMA = json.loads((config.PKG_DIR / "prompts" / "assessment.schema.json").read_text())
ERRORS = (groq.GroqError, ValueError, KeyError, TypeError)  # API errors, bad or empty reply


@cache
def client() -> groq.Groq:
    return groq.Groq(timeout=config.TIMEOUT_S, max_retries=1)


@lru_cache(maxsize=512)  # the same change asked again is answered from memory in microseconds
def call(payload: str) -> str:
    resp = client().chat.completions.create(
        model=config.MODEL, temperature=config.TEMPERATURE, seed=config.SEED,
        max_completion_tokens=config.MAX_TOKENS, **config.REASONING,
        messages=[{"role": "system", "content": PROMPT}, {"role": "user", "content": payload}],
        response_format={"type": "json_schema", "json_schema": {"name": "assessment", "schema": SCHEMA, "strict": True}})
    u = resp.usage
    return json.dumps({"out": json.loads(resp.choices[0].message.content), "model": resp.model,
                       "fingerprint": resp.system_fingerprint, "tokens": [u.prompt_tokens, u.completion_tokens],
                       "groq_ms": round((u.total_time or 0) * 1000)})


def assess(payload: dict, w: dict) -> dict:
    r = json.loads(call(json.dumps(payload, sort_keys=True)))
    values = [w["rating_value"][v] for v in r["out"]["ratings"].values()]
    r["score"] = round(w["worst_weight"] * max(values) + (1 - w["worst_weight"]) * sum(values) / len(values), 2)
    return r
