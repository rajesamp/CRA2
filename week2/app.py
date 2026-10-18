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
from week1.responses import guard
from week2.memory import MemoryStore
from week2.workflow import respond

TRACE_FIELDS = (
    "status", "request_id", "session_id", "orchestration", "memory", "events",
    "retrieved", "provider_used", "request_attempted", "risk_floor",
    "assessment_tool_citations", "source_scope", "model", "tokens", "groq_ms",
)


def project_trace(trace):
    result = {key: trace[key] for key in TRACE_FIELDS if key in trace}
    guard(result)
    return result


def trace_summary(trace):
    lines = ["### Actual execution", f"Status: **{trace.get('status', 'unavailable')}**",
             f"Orchestration: {trace.get('orchestration', 'unavailable')}"]
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


def ui_reply(message, history, mode, session_id, *, memory_store=None):
    answer, trace = respond(message, history, mode, session_id=session_id, memory_store=memory_store)
    projected = project_trace(trace)
    summary = trace_summary(projected)
    guard([answer, summary, projected])
    return answer, summary, projected


def build_app(*, memory_store=None):
    configure_sdk_logging()
    store = MemoryStore() if memory_store is None else memory_store

    def reply(message, history, mode, session_id):
        return ui_reply(message, history, mode, session_id, memory_store=store)

    with gr.Blocks(title="CRA2 · Change risk advisor", analytics_enabled=False) as demo:
        gr.Markdown("# Change risk advisor\nDescribe a change. Review cited evidence and remembered team preferences.\n\n**Advisory only · Synthetic operational snapshots · A human makes the decision.**")
        session_id = gr.State(value=lambda: uuid4().hex)
        mode = gr.Radio(["Local evidence only", "Groq assessment"], value="Local evidence only", label="Review mode")
        with gr.Row():
            with gr.Column(scale=2) as conversation:
                pass
            with gr.Column(scale=1):
                with gr.Accordion("Agent trace", open=False, elem_id="agent-trace"):
                    summary = gr.Markdown("Run a query to inspect actual calls and recalled settings.", elem_id="agent-trace-summary")
                    details = gr.JSON(label="Execution details", elem_id="agent-trace-details", max_height=240)
        with conversation:
            chatbot = gr.Chatbot(label="CRA2 conversation", height=490)
            gr.ChatInterface(reply, chatbot=chatbot, additional_inputs=[mode, session_id],
                additional_outputs=[summary, details], save_history=False, cache_examples=False,
                flagging_mode="never", api_visibility="private", api_name="ui_response",
                description="Use an exact service name. Never enter credentials. Team identity comes from the host configuration.",
                analytics_enabled=False)
        gr.Markdown("**Try:** Remember that checkout-service is always high-risk for our team.\n\nThen open a new browser session and ask: Change checkout-service config timeout from 4 seconds to 400 milliseconds.\n\nTeam preferences persist locally. Conversation history is not restored. Freeze-policy notes do not establish current freeze status.")
    return demo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=7862)
    parser.add_argument("--memory-file", type=Path, help="Trusted host configuration; must be inside CRA2 or /tmp")
    args = parser.parse_args()
    store = MemoryStore() if args.memory_file is None else MemoryStore(args.memory_file)
    root = Path(__file__).resolve().parents[1]
    blocked = [str(root)]
    selected = os.environ.get("CRA2_ENV_FILE")
    if selected:
        blocked.append(str(Path(selected).expanduser().resolve()))
    build_app(memory_store=store).launch(server_name="127.0.0.1", server_port=args.port,
        share=False, inbrowser=False, blocked_paths=blocked, show_error=False,
        enable_monitoring=False, run_history=False, mcp_server=False,
        footer_links=[], max_file_size="1mb")


if __name__ == "__main__":
    main()
