"""Session-local, bounded safety verdicts. No prompt, identity or audit reads."""
from collections import Counter
from datetime import datetime, timezone
from html import escape
import re
from threading import RLock

LIMIT = 100
STAGES = {"input": "Input", "context": "Retrieved context", "output": "Output", "admission": "Admission"}
CODES = {
    "admission_allowed": "Admission screen passed",
    "protected_action_contract": "Protected-action condition matched",
    "prohibited_action_similarity": "Adversarial similarity threshold matched",
    "sensitive_input": "Credential condition matched",
    "admission_blocked": "Admission blocked the request",
    "admission_unavailable": "Admission check unavailable",
    "cooldown": "Temporary security pause is active",
    "invalid_input": "Input format requires correction",
    "contract_valid": "Configured contract passed",
    "protected_action": "Protected-action condition matched",
    "untrusted_context": "Untrusted or malformed evidence condition matched",
    "unsupported_output": "Approval-language or advisory contract matched",
    "rail_unavailable": "No verified NeMo verdict",
    "not_reached": "Stopped before this check",
    "not_required": "No retrieval was required for this response",
}
OUTCOMES = {"allow": "Passed", "block": "Blocked", "unavailable": "Unavailable",
            "not_reached": "Not reached", "not_required": "Not required"}


def admission_event(decision):
    """Project the gate's decision; never copy arbitrary classifier fields."""
    verdict = decision.get("verdict", {})
    reason = verdict.get("reason")
    blocked = decision.get("blocked") is True
    unavailable = blocked and decision.get("reason") == "unavailable"
    code = "admission_blocked" if blocked else "admission_allowed"
    if reason in {"protected_action_contract", "prohibited_action_similarity"} and blocked:
        code = reason
    if blocked and decision.get("reason") == "sensitive":
        code = "sensitive_input"
    if verdict.get("classification") == "invalid_input":
        code = "invalid_input"
    if unavailable:
        code = "admission_unavailable"
    if decision.get("cooldown") is True:
        code = "cooldown"
    return {"engine": "admission", "stage": "admission", "code": code,
            "outcome": "unavailable" if unavailable else "block" if blocked else "allow",
            "executed": not unavailable and code != "cooldown"}


def project_events(trace):
    """Closed vocabulary prevents rejected contents from reaching the panel."""
    result = []
    admission = trace.get("admission")
    if isinstance(admission, dict):
        candidates = [admission, *trace.get("rails", [])]
    else:
        candidates = list(trace.get("rails", []))
    for event in candidates[:12]:
        if not isinstance(event, dict) or event.get("stage") not in STAGES:
            continue
        if event.get("engine") not in {"admission", "nemoguardrails"}:
            continue
        outcome = event.get("outcome")
        code = event.get("code")
        if outcome not in {"allow", "block", "unavailable"} or code not in CODES:
            outcome, code = "unavailable", "rail_unavailable"
        if event.get("executed") is not True and outcome == "allow":
            outcome, code = "unavailable", "rail_unavailable"
        result.append({"stage": event["stage"], "engine": event["engine"],
                       "outcome": outcome, "code": code, "executed": event.get("executed") is True})
    seen = {e["stage"] for e in result}
    for stage in ("input", "context", "output"):
        if stage in seen:
            continue
        outcome = "not_reached"
        if stage == "context" and trace.get("status") in {"help", "out_of_scope", "needs_clarification"}:
            outcome = "not_required"
        if stage == "input" and trace.get("status") in {"unavailable", "guardrails_unavailable"} and not seen.intersection({"input", "output"}):
            outcome = "unavailable"
        result.append({"stage": stage, "engine": "nemoguardrails", "outcome": outcome,
                       "code": "rail_unavailable" if outcome == "unavailable" else outcome, "executed": False})
    return result


def recovery_stages(report):
    """Build four ordered receipts from known stage/engine/decision combinations."""
    stages = []
    receipts = [report.get("admission"), *report.get("rails", [])]
    stopped = False
    for stage in ("admission", "input", "context", "output"):
        engine = "admission" if stage == "admission" else "nemoguardrails"
        matches = [r for r in receipts if isinstance(r, dict) and r.get("stage") == stage]
        outcome = "not_reached" if stopped else "unavailable"
        if not matches and not stopped and stage == "context" and report.get("context_required") is False:
            outcome = "not_required"
        code = ("admission_unavailable" if stage == "admission" else "rail_unavailable") if outcome == "unavailable" else outcome
        executed = False
        if len(matches) == 1:
            r = matches[0]
            allow = {"admission_allowed", "invalid_input"} if stage == "admission" else {"contract_valid"}
            block = {"admission": {"protected_action_contract", "prohibited_action_similarity",
                                   "sensitive_input", "admission_blocked", "cooldown", "invalid_input"},
                     "input": {"protected_action"}, "context": {"untrusted_context"},
                     "output": {"unsupported_output"}}[stage]
            valid = (r.get("outcome") == "allow" and r.get("code") in allow and r.get("executed") is True
                     or r.get("outcome") == "block" and r.get("code") in block
                     and r.get("executed") is (r["code"] != "cooldown"))
            if r.get("engine") == engine and valid and not stopped:
                outcome, code, executed = r["outcome"], r["code"], r["executed"]
            else:
                outcome = "unavailable"
                code = "admission_unavailable" if stage == "admission" else "rail_unavailable"
        stages.append(dict(stage=stage, engine=engine, outcome=outcome, code=code, executed=executed))
        stopped = stopped or outcome in {"unavailable", "block"}
    return stages


class SessionActivity:
    """One server-side Gradio state per browser session/verified principal.

    Updates mutate this instance under a lock, so concurrent chat/report requests
    cannot overwrite each other's events. Gradio deep-copies initial state.
    """
    def __init__(self):
        self._lock = RLock()
        self._rows = []
        self._sequence = 0

    def __deepcopy__(self, memo):
        return SessionActivity()

    def append(self, source, trace):
        with self._lock:
            self._sequence += 1
            self._rows.append({"number": self._sequence,
                               "time": datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
                               "source": "Chat" if source == "chat" else "Incidents & rollback",
                               "events": recovery_stages(trace) if source == "recovery" else project_events(trace),
                               "gap": trace.get("telemetry_status") == "unavailable" and source == "recovery",
                               "review": trace.get("request_id") if re.fullmatch(r"[0-9a-f]{32}", str(trace.get("request_id"))) else None})
            self._rows = self._rows[-LIMIT:]
            return self.html()

    def clear(self):
        with self._lock:
            self._rows.clear()
            self._sequence = 0
            return self.html()

    def html(self):
        with self._lock:
            counts = Counter(e["outcome"] for row in self._rows for e in row["events"])
            parts = ['<section class="cra-guardrails"><h2>Guardrail activity</h2>',
                     '<p>Current session only · Last 100 requests · Verdict metadata only</p>',
                     '<p>A matched condition is not proof of malicious intent. No prompts, account identities or private audit records are shown.</p>']
            if not self._rows:
                parts.append('<p>No checks recorded yet. Run a chat or incident analysis to see its checks here.</p>')
            else:
                parts.append(f'<p><strong>{len(self._rows)} requests · {counts["allow"]} passed checks · {counts["block"]} blocked checks · {counts["unavailable"]} unavailable checks</strong></p>')
            for row in reversed(self._rows):
                parts.append(f'<article><h3>Request {row["number"]} · {row["source"]} · {row["time"]}</h3><ul>')
                for event in row["events"]:
                    engine = "NeMo" if event["engine"] == "nemoguardrails" else "Admission"
                    condition = CODES[event["code"]]
                    if event["code"] == "contract_valid":
                        condition = {"input": "Protected-action contract passed",
                                     "context": "Evidence shape and injection-pattern checks passed",
                                     "output": "Approval-language and advisory contract passed"}.get(event["stage"], condition)
                    parts.append('<li><strong>' + engine + ' / ' + STAGES[event["stage"]] +
                                 ': ' + OUTCOMES[event["outcome"]] + '</strong> — ' +
                                 escape(condition) + '</li>')
                parts.append('</ul>')
                if row["review"]:
                    parts.append('<p>Review ID ' + escape(str(row["review"])) + '</p>')
                if row["gap"]:
                    parts.append('<p>Review record confirmation incomplete.</p>')
                parts.append('</article>')
            parts.append('<p>NeMo runs configured local contract checks. The host submits retrieved context for checking. These checks do not prove resistance to every jailbreak or establish factual correctness.</p></section>')
            return "".join(parts)


def record_activity(activity, source, trace):
    state = activity if isinstance(activity, SessionActivity) else SessionActivity()
    return state, state.append(source, trace)


def clear_activity(activity):
    state = activity if isinstance(activity, SessionActivity) else SessionActivity()
    return state, state.clear()


CSS = ".cra-guardrails{line-height:1.65;padding:12px}.cra-guardrails article{border-left:3px solid #66ab96;padding:8px 16px;margin:16px 0}.cra-guardrails h3{font-weight:600}"
