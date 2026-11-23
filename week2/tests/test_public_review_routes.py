"""Regression cases use the public schedule through the same guarded callbacks as the UI."""
import json
from pathlib import Path

import pytest

from week2.abuse import AbuseGate
from week2.app import guarded_ui_reply
from week2.incident_rollback import FIELDS, guarded_analyze
from week2.memory import MemoryStore
from week2.owner_audit import OwnerAuditStore

PACKET = Path(__file__).resolve().parents[2] / "evals/answer-quality/development-v1.json"
CASES = {r["id"]: r["input"] for r in json.loads(PACKET.read_bytes())["cases"]}


@pytest.mark.parametrize("case,fragments", [
    ("public-analogue", ["CX-104", "payment-gateway", "cross-service", "data/incidents.json"]),
    ("public-health", ["checkout-service", "Healthy", "freshness", "Verify", "catalog:checkout-service.status"]),
    ("public-ambiguous", ["service", "limit", "?"]),
    ("public-absent", ["voucher-worker", "runbook", "rollback"]),
])
def test_chat_delivers_requested_review(case, fragments, tmp_path):
    answer, _, trace = guarded_ui_reply(CASES[case]["message"], [], "Local evidence only", case,
        gate=AbuseGate(store=OwnerAuditStore(tmp_path / "audit.db")), client=case,
        memory_store=MemoryStore(tmp_path / "memory.db"))
    assert trace["status"] in {"tool_evidence", "incident_lookup", "needs_clarification", "no_recovery_record"}
    assert all(fragment.lower() in answer.lower() for fragment in fragments), answer
    assert trace["admission"]["outcome"] == "allow" and not trace["request_attempted"]


@pytest.mark.parametrize("case,fragments", [
    ("public-schema", ["reverse migration", "Direct callers", "checkout-service", "catalog:inventory-service.rollback"]),
    ("public-cause", ["data/incidents.json#CX-107", "online option", "not causal proof"]),
    ("public-freeze", ["catalog:auth-service.freeze_window_active", "freeze has ended", "declaration:summary", "owner"]),
])
def test_recovery_delivers_requested_review(case, fragments, tmp_path):
    inputs = CASES[case]
    html, result = guarded_analyze([inputs[name] for name in FIELDS],
        gate=AbuseGate(store=OwnerAuditStore(tmp_path / "audit.db")), client=case)
    assert result["admission"]["outcome"] == "allow", result["admission"]
    assert result["status"] == "ok" and not result["provider_used"]
    assert [e["outcome"] for e in result["rails"]] == ["allow"] * 3
    assert all(fragment.lower() in html.lower() for fragment in fragments), html
