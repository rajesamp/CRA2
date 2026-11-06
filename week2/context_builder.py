"""Fresh, bounded per-action inputs resolved from host-owned evidence and policy.

History contains validated observation records only. Raw conversations, provider
responses, preference notes and owner records are not accepted by this API.
"""

import json
import hashlib
import math
import unicodedata
from copy import deepcopy

from cra2.public_evidence import validate_public_hit
from cra2.team_settings import SETTING_FIELDS
from week1.responses import guard
from week2.contracts import (
    ContractError, validate_result, validate_semantic_context, validate_semantic_state,
)
from week2.semantic_state import digest

MODES = ("full", "threshold", "sac")
MAX_CONTEXT_BYTES = 65536
_HIT_FIELDS = {"chunk_id", "doc_id", "title", "source", "kind", "service",
               "source_dataset", "text", "score"}


def context_json(value):
    """Canonical bounded JSON for source content, preserving ordinary whitespace.

    The stricter P1 state serializer remains unchanged. Source passages may use
    newlines and tabs; other controls and invalid Unicode still fail closed.
    """
    try:
        guard(value)
        def visit(item):
            if isinstance(item, str):
                if any(unicodedata.category(char).startswith("C") and char not in "\n\r\t"
                       for char in item):
                    raise ValueError
            elif isinstance(item, dict):
                for key, val in item.items():
                    if not isinstance(key, str):
                        raise ValueError
                    visit(key)
                    visit(val)
            elif isinstance(item, list):
                for val in item:
                    visit(val)
            elif item is not None and type(item) not in (bool, int, float):
                raise ValueError
        visit(value)
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False,
                         allow_nan=False, separators=(",", ":"))
        if len(raw.encode("utf-8")) > MAX_CONTEXT_BYTES:
            raise ValueError
        return raw
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ContractError("invalid_action_context") from None


def content_digest(value):
    return hashlib.sha256(context_json(value).encode("utf-8")).hexdigest()


def _size(value):
    # Measure before the common guard's 64 KiB limit so overflow gets its own
    # protected budget error. No content escapes this internal size calculation.
    return len(json.dumps(value, sort_keys=True, ensure_ascii=False,
                          allow_nan=False, separators=(",", ":")).encode("utf-8"))


def _policy(policy, authority):
    fields = set(SETTING_FIELDS)
    if (not isinstance(policy, dict)
            or set(policy) != {"team", "effective", "sources", "conflicts"}
            or not isinstance(policy["team"], str)
            or not 1 <= len(policy["team"]) <= 100 or not policy["team"].strip()
            or not isinstance(policy["effective"], dict)
            or set(policy["effective"]) != fields
            or any(type(value) is not bool for value in policy["effective"].values())
            or not isinstance(policy["sources"], dict) or set(policy["sources"]) != fields
            or any(not isinstance(value, str) for value in policy["sources"].values())
            or not isinstance(policy["conflicts"], list) or len(policy["conflicts"]) > 64):
        raise ContractError("invalid_action_context")
    if (digest(policy) != authority["policy_digest"]
            or sorted(set(policy["sources"].values())) != authority["policy_refs"]):
        raise ContractError("invalid_action_context")
    for field, source in policy["sources"].items():
        allowed = {f"default:{field}", f"change:settings.{field}",
                   f"catalog:{authority['service']}.{field}",
                   f"team:{authority['service']}.{field}"}
        if field == "high_risk":
            allowed.add(f"memory:{authority['service']}.high_risk")
        if source not in allowed:
            raise ContractError("invalid_action_context")
    seen = set()
    for conflict in policy["conflicts"]:
        if (not isinstance(conflict, dict)
                or set(conflict) != {"field", "requested", "effective", "source"}
                or conflict["field"] not in fields or conflict["field"] in seen
                or type(conflict["requested"]) is not bool
                or type(conflict["effective"]) is not bool
                or conflict["requested"] == conflict["effective"]
                or conflict["effective"] != policy["effective"][conflict["field"]]
                or conflict["source"] != policy["sources"][conflict["field"]]):
            raise ContractError("invalid_action_context")
        seen.add(conflict["field"])
    return deepcopy(policy)


def _historical(raw, record, service):
    if not isinstance(raw, dict) or set(raw) != _HIT_FIELDS:
        raise ContractError("invalid_action_context")
    for field, limit in (("chunk_id", 200), ("doc_id", 200), ("title", 300),
                         ("source", 500), ("text", 16000)):
        if not isinstance(raw[field], str) or not raw[field].strip() or len(raw[field]) > limit:
            raise ContractError("invalid_action_context")
    if (raw["chunk_id"] != record["id"] or raw["source"] != record["source_id"]
            or raw["chunk_id"].startswith("public-")
            or raw["doc_id"].startswith("public-")
            or raw["service"] not in (None, service)
            or raw["service"] != record.get("source_service", record["service"])
            or raw["kind"] not in ("incident", "postmortem", "runbook", "policy")
            or raw["source_dataset"] not in ("synthetic", "sanitized_samples", "corpus_markdown")
            or type(raw["score"]) not in (int, float) or not math.isfinite(raw["score"])
            or not -1 <= raw["score"] <= 1
            or (raw["service"] is None and raw["kind"] in ("incident", "postmortem"))):
        raise ContractError("invalid_action_context")


def _external_public(raw, record):
    # A matching digest only proves that the caller resealed the supplied bytes.
    # Recheck the canonical public document so source facts and CRA2 inference
    # cannot be rewritten together with its digest or promoted to local history.
    try:
        validate_public_hit(raw)
        if (raw["chunk_id"] != record["id"] or raw["source"] != record["source_id"]
                or raw["service"] != record["source_service"]):
            raise ValueError
    except (ValueError, TypeError, KeyError):
        raise ContractError("invalid_action_context") from None


def _resolve(reference, record, evidence_store, service):
    if reference not in evidence_store:
        raise ContractError("invalid_action_context")
    raw = evidence_store[reference]
    if content_digest(raw) != record["content_digest"]:
        raise ContractError("invalid_action_context")
    if record["origin"] == "retrieve":
        if record["kind"] == "external_public":
            _external_public(raw, record)
        else:
            _historical(raw, record, service)
    else:
        validate_result(record["origin"], service, raw)
        if (raw["status"] != "ok" or raw["source"]["path"] != record["source_id"]
                or raw["source"]["kind"] != record["kind"]
                or reference not in raw["evidence"]):
            raise ContractError("invalid_action_context")
    resolved = {"kind": record["kind"], "source_id": record["source_id"],
                "content": deepcopy(raw)}
    if "source_service" in record:
        resolved["source_service"] = record["source_service"]
    return resolved


def build_context(state, authority, *, evidence_store, policy, mode="sac",
                  threshold_bytes=8192, max_bytes=32768):
    """Resolve a new model input without mutating state or its external sources.

    ``full`` retains each validated action observation. ``threshold`` clears that
    history whenever its UTF-8 JSON exceeds the threshold, then starts accumulating
    again. ``sac`` omits history. All modes retain the same current evidence and
    authoritative policy; byte overflow fails rather than dropping references.
    """
    try:
        if (not isinstance(mode, str) or mode not in MODES
                or type(threshold_bytes) is not int or not 1 <= threshold_bytes <= MAX_CONTEXT_BYTES
                or type(max_bytes) is not int or not 1 <= max_bytes <= MAX_CONTEXT_BYTES):
            raise ContractError("invalid_action_context")
        trusted = validate_semantic_context(authority)
        compact = validate_semantic_state(state, trusted)
        sources = {record["id"]: record for record in trusted["evidence"]}
        if not isinstance(evidence_store, dict) or not evidence_store.keys() <= sources.keys():
            raise ContractError("invalid_action_context")
        evidence = {ref: _resolve(ref, sources[ref], evidence_store, compact["service"])
                    for ref in compact["evidence_ids"]}
        accepted = trusted["action_results"][:len(compact["completed_action_ids"])]
        context = {
            "context_mode": mode, "objective": compact["objective"],
            "service": compact["service"], "next_action": compact["next_action"],
            "semantic_state": compact,
            "current_observation": deepcopy(accepted[-1]) if accepted else None,
            "evidence": evidence, "policy": _policy(policy, trusted),
            "compaction_count": len(accepted) if mode == "sac" else 0,
        }
        if mode != "sac":
            history = []
            for action in accepted:
                # Resolve evidence once above; history records references only.
                history.append(deepcopy(action))
                if mode == "threshold" and _size(history) > threshold_bytes:
                    history = []
                    context["compaction_count"] += 1
            context["action_history"] = history
        if _size(context) > max_bytes:
            raise ContractError("context_budget_exceeded")
        context_json(context)
        return context
    except ContractError as exc:
        if exc.code == "context_budget_exceeded":
            raise
        raise ContractError("invalid_action_context") from None
    except (KeyError, TypeError, ValueError, UnicodeError, RecursionError):
        raise ContractError("invalid_action_context") from None
