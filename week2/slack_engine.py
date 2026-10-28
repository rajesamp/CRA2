"""Reuse CRA2 admission, graph and concise answers; no Slack delivery here."""

from dataclasses import dataclass, field
from uuid import uuid4

from cra2.advisor import ADVISORY
from cra2.secrets import reject_credentials
from week2.abuse import AbuseGate
from week2.app import guarded_ui_reply, retain_trace
from week2.memory import MemoryStore, MemoryUnavailable
from week2.preferences import parse_command
from week2.slack_ui import with_service


class ReadOnlyPreferences:
    def __init__(self, store):
        self.store = store

    def read(self, service):
        return self.store.read(service)

    def write(self, *_args, **_kwargs):
        raise MemoryUnavailable("memory_changes_disabled")


@dataclass
class Session:
    session_id: str = field(default_factory=lambda: uuid4().hex)
    turn: int = 0
    history: list = field(default_factory=list)
    traces: list = field(default_factory=list)


class SlackEngine:
    def __init__(self, credentials, *, gate=None, memory_store=None):
        self.credentials = tuple(credentials)
        self.gate = gate if gate is not None else AbuseGate(additional_credentials=self.credentials)
        self.memory = ReadOnlyPreferences(memory_store if memory_store is not None else MemoryStore())

    def ask(self, origin, question, service, session):
        try:
            effective = with_service(question, service)
            answer, _, trace = guarded_ui_reply(effective, session.history, "Groq assessment", session.session_id,
                gate=self.gate, client="slack:" + origin.team + ":" + origin.user, memory_store=self.memory)
            if trace["status"] == "memory_unavailable" and parse_command(effective):
                answer = "Slack can read team preferences. Changes to team policy must be made by the app owner in the local app.\n\n" + ADVISORY
                trace.update(status="preference_read_only", response_details=answer)
            if trace["status"] == "security_blocked":
                seconds, reason = self.gate.remaining("slack:" + origin.team + ":" + origin.user)
                prefix = "Adversary actions noted." if reason == "adversarial" else "Request paused."
                answer = f"{prefix} Please wait {seconds} seconds before asking again."
            reject_credentials([answer, trace], additional=self.credentials)
            session.turn += 1
            trace["turn"] = session.turn
            session.traces = retain_trace(session.traces, trace)
            safe_question = trace.get("question", "Input withheld")
            session.history = (session.history + [{"role": "user", "content": safe_question},
                {"role": "assistant", "content": answer}])[-100:]
            return answer
        except Exception:
            return "The assessment is unavailable. No risk rating is assigned.\n\n" + ADVISORY
