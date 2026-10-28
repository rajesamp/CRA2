"""Task 18: local Gradio chat with actual MCP calls and recalled policy trace."""

import argparse
import os
from pathlib import Path
from uuid import uuid4

# All generated UI files stay inside the permitted local workspace.
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
os.environ["GRADIO_TEMP_DIR"] = str(Path(__file__).with_name(".local") / "gradio")

import gradio as gr

from cra2.secrets import configure_sdk_logging
from cra2.advisor import ADVISORY, LEVELS, _inline
from week1.responses import guard
from week2.memory import MemoryStore
from week2.workflow import load_copy, respond
from week2.abuse import AbuseGate
from week2.owner_audit import OwnerAuditStore
from week2.presentation import review_summary

TRACE_FIELDS = (
    "status", "request_id", "session_id", "orchestration", "memory", "events",
    "retrieved", "provider_used", "request_attempted", "risk_floor",
    "assessment_tool_citations", "source_scope", "model", "tokens", "groq_ms",
    "assessment", "response_details", "turn", "review_mode", "question", "topic",
)
EMPTY_TRACE = "Run a query to inspect its supporting evidence and execution details."
MAX_TRACES = 50


def project_trace(trace):
    result = {key: trace[key] for key in TRACE_FIELDS if key in trace}
    guard(result)
    return result


def trace_summary(trace):
    heading = f"Turn #{trace['turn']} · Actual execution" if "turn" in trace else "Actual execution"
    lines = [f"### {heading}", f"Status: **{trace.get('status', 'unavailable')}**",
             f"Orchestration: {trace.get('orchestration', 'unavailable')}"]
    if "review_mode" in trace:
        lines.append(f"Review mode: **{trace['review_mode']}**")
    if "question" in trace:
        lines.append("Question: " + _inline(trace["question"]))
    memory = trace.get("memory", {})
    lines.append("\n### Team preferences")
    lines.append(f"Memory: **{memory.get('status', 'not_accessed')}**")
    record = memory.get("record")
    if record:
        effective = memory["effective_policy"]
        lines += [f"Remembered high-risk flag: **{str(record['high_risk']).lower()}**",
                  f"Effective high-risk policy: **{str(effective['effective']['high_risk']).lower()}**",
                  f"Source: `{effective['sources']['high_risk']}`"]
        if effective["conflicts"]:
            lines.append("Configured policy takes precedence; see conflict details below.")
        if record["freeze_notes"]:
            lines.append("Freeze-policy note recalled as unverified policy text; see details.")
    lines.append("\n### MCP tool calls")
    calls = [event for event in trace.get("events", []) if event.get("event") == "tool_result"]
    for event in calls:
        result = event["output"]
        lines.append(f"- `{event['tool']}({event['input']['service_name']})` → **{result['status']}**")
        if result["status"] == "ok":
            if "health" in result:
                lines.append(f"  Recorded health: {result['health']}; freeze: {result['freeze_window']['status']}.")
            else:
                lines.append("  Direct dependencies: " + (", ".join(result["dependencies"]["direct"]) or "[]"))
        else:
            lines.append(f"  Protected error: `{result['error']['code']}`")
    if not calls:
        lines.append("No tool result was returned for this request.")
    lines.append("\n**Synthetic snapshots · freshness unknown · human decision required.**")
    return "\n\n".join(lines)


def chat_response(answer, trace):
    """Present outcomes from structured execution facts, never parse diagnostic prose."""
    try:
        copy = load_copy()
    except (OSError, ValueError):
        return "The request could not be assessed. No risk rating is assigned.\n\n" + ADVISORY
    key = "chat_" + trace.get("status", "unavailable")
    if key not in copy:
        return answer
    if trace.get("status") == "assessed":
        level = trace.get("assessment", {}).get("risk_level")
        if level not in LEVELS:
            return copy["chat_unavailable"] + "\n\n" + ADVISORY
        text = copy[key].format(level=level.upper())
    else:
        text = copy[key]
    if trace.get("status") in {"assessed", "evidence_only"}:
        text = "\n\n".join([text, *review_summary(trace, copy)])
    return text + "\n\n" + ADVISORY


def ui_reply(message, history, mode, session_id, *, memory_store=None):
    answer, trace = respond(message, history, mode, session_id=session_id, memory_store=memory_store)
    turn = 1 + sum(1 for item in (history or []) if isinstance(item, dict) and item.get("role") == "user")
    question = message if trace.get("status") != "unavailable" and isinstance(message, str) and 0 < len(message) <= 4000 else "Input withheld"
    review_mode = mode if mode in ("Local evidence only", "Groq assessment") else "Unavailable"
    projected = project_trace(dict(trace, response_details=answer, turn=turn, review_mode=review_mode, question=question))
    answer = chat_response(answer, projected)
    summary = trace_summary(projected)
    guard([answer, summary, projected])
    return answer, summary, projected


def retain_trace(traces, trace):
    """Keep bounded session snapshots; retry/branch replaces the same or later turns."""
    projected = project_trace(trace)
    earlier = [item for item in traces if item["turn"] < projected["turn"]]
    return (earlier + [projected])[-MAX_TRACES:]


def trace_choices(traces):
    return [(f"Turn #{item['turn']} · {item['review_mode']}", item["turn"]) for item in traces]


def select_trace(turn, traces):
    """Viewing a snapshot never invokes the workflow or rereads team memory."""
    trace = next((item for item in traces if item["turn"] == turn), None)
    if trace is None:
        return EMPTY_TRACE, {}, "", gr.update(label="Agent trace", open=False)
    label = f"Agent trace · Turn #{trace['turn']} · {trace['review_mode']}"
    return trace_summary(trace), trace, trace.get("response_details", ""), gr.update(label=label, open=True)


def admin_trace_view(turn, traces, unlocked):
    """Only project server-held snapshots after the session's demo gate opens."""
    if unlocked is not True:
        return ("Admin is locked.", {}, "", gr.update(label="Agent trace", open=False),
                gr.update(choices=[], value=None, interactive=False))
    return (*select_trace(turn, traces),
            gr.update(choices=trace_choices(traces), value=turn, interactive=True))


def unlock_admin(pin, traces):
    """Any four ASCII digits: an explicitly chosen demo gate, not authentication."""
    unlocked = isinstance(pin, str) and len(pin) == 4 and pin.isascii() and pin.isdecimal()
    status = gr.update(value="" if unlocked else "Enter exactly four digits to open the demo panel.", visible=not unlocked)
    turn = traces[-1]["turn"] if unlocked and traces else None
    return (unlocked, gr.update(value=""), status, gr.update(visible=not unlocked),
            gr.update(visible=unlocked), *admin_trace_view(turn, traces, unlocked))


def lock_admin():
    return (False, gr.update(value=""), gr.update(value="", visible=False), gr.update(visible=True),
            gr.update(visible=False), *admin_trace_view(None, [], False))


def protected_reply(history, mode, session_id):
    answer = "That request was blocked. Please try again after the temporary pause."
    trace = project_trace({"status": "security_blocked", "request_id": uuid4().hex,
        "session_id": session_id, "turn": 1 + sum(1 for item in (history or []) if isinstance(item, dict) and item.get("role") == "user"),
        "review_mode": mode if mode in ("Local evidence only", "Groq assessment") else "Unavailable",
        "question": "Request withheld", "response_details": answer, "orchestration": "not_started",
        "memory": {"status": "not_accessed"}, "retrieved": [], "events": [],
        "provider_used": False, "request_attempted": False})
    return answer, trace_summary(trace), trace


def guarded_ui_reply(message, history, mode, session_id, *, gate, client, memory_store=None):
    admission = gate.admit(message, client)
    if admission["blocked"]:
        return protected_reply(history, mode, session_id)
    result = ui_reply(message, history, mode, session_id, memory_store=memory_store)
    if result[2]["status"] == "out_of_scope":
        if not gate.record_out_of_scope(message, client, admission["verdict"]):
            return protected_reply(history, mode, session_id)
    return result


def cooldown_view(gate, client):
    seconds, reason = gate.remaining(client)
    if reason == "adversarial":
        text = f"Adversary actions noted. Chat blocked for {seconds} secs."
    elif reason == "sensitive":
        text = f"Sensitive input blocked. Chat paused for {seconds} secs."
    else:
        text = f"Security check unavailable. Chat paused for {seconds} secs."
    markup = '<div role="alert" aria-live="polite" style="min-height:490px;display:flex;align-items:center;justify-content:center;text-align:center;font-size:1.4rem;font-weight:600;padding:2rem">' + text + '</div>'
    return gr.update(value=markup if seconds else "", visible=bool(seconds)), gr.update(visible=not seconds), gr.update(active=bool(seconds))


def request_client(request):
    host = request.client.host if request is not None and request.client is not None else None
    if not isinstance(host, str) or not host or len(host) > 200:
        raise ValueError("Trusted client identity unavailable")
    return host


def build_app(*, memory_store=None, abuse_gate=None):
    configure_sdk_logging()
    store = MemoryStore() if memory_store is None else memory_store
    gate = AbuseGate() if abuse_gate is None else abuse_gate

    def reply(message, history, mode, session_id, traces, admin_unlocked, request: gr.Request):
        client = request_client(request)
        answer, _, trace = guarded_ui_reply(message, history, mode, session_id, gate=gate, client=client, memory_store=store)
        updated = retain_trace(traces, trace)
        summary, details, supporting, panel, choices = admin_trace_view(trace["turn"], updated, admin_unlocked)
        # Keep the panel's current open/closed state on a new answer.
        panel.pop("open", None)
        return answer, summary, details, supporting, panel, updated, choices, *cooldown_view(gate, client)

    def cooldown(request: gr.Request):
        try:
            return cooldown_view(gate, request_client(request))
        except (ValueError, AttributeError):
            return gr.update(value="Security check unavailable.", visible=True), gr.update(visible=False), gr.update(active=False)

    def reset_trace(admin_unlocked):
        *view, choices = admin_trace_view(None, [], admin_unlocked)
        return (*view, [], choices)

    def undo_trace(traces, admin_unlocked):
        updated = traces[:-1]
        turn = updated[-1]["turn"] if updated else None
        *view, choices = admin_trace_view(turn, updated, admin_unlocked)
        return (*view, updated, choices)

    with gr.Blocks(title="CRA2 · Change risk advisor", analytics_enabled=False) as demo:
        gr.Markdown("# Change risk advisor\n**Advisory only · Synthetic evidence · A human makes the decision.**")
        session_id = gr.State(value=lambda: uuid4().hex)
        trace_history = gr.State(value=[])
        admin_unlocked = gr.State(value=False)
        timer = gr.Timer(value=.5, active=False)
        with gr.Tabs():
            with gr.Tab("Change Risk Advisor"):
                with gr.Column() as conversation:
                    mode = gr.Radio(["Local evidence only", "Groq assessment"], value="Local evidence only", label="Review mode")
            with gr.Tab("Admin"):
                gr.Markdown("## Admin\nSession trace history and execution details.")
                admin_status = gr.Markdown(visible=False, elem_id="admin-status")
                with gr.Group() as login_controls:
                    pin = gr.Textbox(label="Demo PIN", type="password", placeholder="Enter any four digits", max_lines=1)
                    unlock = gr.Button("Unlock Admin", variant="primary")
                with gr.Group(visible=False, elem_id="admin-trace-controls") as admin_controls:
                    lock = gr.Button("Lock Admin")
                    turn_selector = gr.Dropdown(label="Agent trace history", choices=[], value=None,
                        interactive=False, allow_custom_value=False, elem_id="agent-trace-turns",
                        info="Select a turn from this chat. The latest 50 are kept until you clear or refresh.")
                    with gr.Accordion("Agent trace", open=False, elem_id="agent-trace") as trace_panel:
                        summary = gr.Markdown(EMPTY_TRACE, elem_id="agent-trace-summary")
                        with gr.Accordion("Evidence and policy details", open=False):
                            supporting = gr.Markdown(elem_id="agent-supporting-details")
                        details = gr.JSON(value={}, label="Execution details", elem_id="agent-trace-details", max_height=240)
        with conversation:
            notice = gr.HTML(visible=False, elem_id="security-notice")
            with gr.Group(elem_id="chat-controls") as controls:
                chatbot = gr.Chatbot(label="CRA2 conversation", height=490, elem_id="agent-chat")
                gr.ChatInterface(reply, chatbot=chatbot, additional_inputs=[mode, session_id, trace_history, admin_unlocked],
                    additional_outputs=[summary, details, supporting, trace_panel, trace_history, turn_selector, notice, controls, timer], save_history=False, cache_examples=False,
                    flagging_mode="never", api_visibility="private", api_name="ui_response",
                    description="Name the service and describe the proposed change. Never enter credentials.",
                    analytics_enabled=False)
            chatbot.clear(reset_trace, inputs=[admin_unlocked], outputs=[summary, details, supporting, trace_panel, trace_history, turn_selector], queue=False, api_visibility="private")
            chatbot.undo(undo_trace, inputs=[trace_history, admin_unlocked], outputs=[summary, details, supporting, trace_panel, trace_history, turn_selector], queue=False, api_visibility="private")
            gr.Markdown("Ask **What is this app?**, **What services do you support?**, or **How do I get started?** Supporting evidence is available in **Admin → Agent trace**.")
            gr.Markdown("Out-of-scope questions and flagged requests are recorded privately for app-owner review.")
        trace_outputs = [summary, details, supporting, trace_panel, turn_selector]
        admin_outputs = [admin_unlocked, pin, admin_status, login_controls, admin_controls, *trace_outputs]
        unlock.click(unlock_admin, inputs=[pin, trace_history], outputs=admin_outputs, queue=False, api_visibility="private")
        pin.submit(unlock_admin, inputs=[pin, trace_history], outputs=admin_outputs, queue=False, api_visibility="private")
        lock.click(lock_admin, outputs=admin_outputs, queue=False, api_visibility="private")
        turn_selector.input(admin_trace_view, inputs=[turn_selector, trace_history, admin_unlocked], outputs=trace_outputs, queue=False, api_visibility="private")
        timer.tick(cooldown, outputs=[notice, controls, timer], queue=False, api_visibility="private")
        demo.load(cooldown, outputs=[notice, controls, timer], queue=False, api_visibility="private")
    return demo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=7862)
    parser.add_argument("--memory-file", type=Path, help="Trusted host configuration; must be inside CRA2 or /tmp")
    parser.add_argument("--audit-file", type=Path, help="Trusted owner-only audit path inside CRA2 or /tmp")
    args = parser.parse_args()
    # Direct loopback app: forwarded headers must not spoof cooldown identity.
    os.environ["FORWARDED_ALLOW_IPS"] = ""
    store = MemoryStore() if args.memory_file is None else MemoryStore(args.memory_file)
    root = Path(__file__).resolve().parents[1]
    blocked = [str(root)]
    selected = os.environ.get("CRA2_ENV_FILE")
    if selected:
        blocked.append(str(Path(selected).expanduser().resolve()))
    gate = AbuseGate(store=OwnerAuditStore(args.audit_file)) if args.audit_file is not None else None
    build_app(memory_store=store, abuse_gate=gate).launch(server_name="127.0.0.1", server_port=args.port,
        share=False, inbrowser=False, blocked_paths=blocked, show_error=False,
        enable_monitoring=False, run_history=False, mcp_server=False,
        footer_links=[], max_file_size="1mb")


if __name__ == "__main__":
    main()
