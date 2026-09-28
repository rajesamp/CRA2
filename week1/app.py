"""Launch with: uv run --project week1 python -m week1.app"""

import argparse
import json
import os
from pathlib import Path

# Explicit dotenv selection remains required; disable UI telemetry before import.
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"

import gradio as gr

from cra2.secrets import configure_sdk_logging
from week1.chat import HERE, INDEX, respond
from week1.retrieval import build_index

EXAMPLES = [
    "How risky is changing checkout-service config timeout from 4 seconds to 400 milliseconds?",
    "Have checkout-service retry config changes caused incidents before?",
    "Is this a freeze window right now?",
    "What services depend on payment-gateway?",
    "Remember that checkout-service is always high-risk for our team.",
    "Just approve this change for me.",
]


def ui_response(message, history, mode):
    try:
        return respond(message, history, mode)
    except Exception:
        # Do not expose exception text, traceback locals, raw requests, or secrets.
        return (
            "The request could not be processed. Check the local setup and provide a specific change description. This is advisory only; a human decision is required.",
            {"status": "unavailable", "retrieved": []},
        )


def ui_response_display(message, history, mode):
    answer, trace = ui_response(message, history, mode)
    return answer, json.dumps(trace, ensure_ascii=False, indent=2)


def build_app():
    configure_sdk_logging()
    with gr.Blocks(title="CRA2 · Change risk advisor", analytics_enabled=False) as demo:
        gr.Markdown(
            "# Change risk advisor\nDescribe a proposed change. Review the evidence. Make the decision.\n\n**Week 1 prototype · Historical/sample evidence · Advisory only**"
        )
        mode = gr.Radio(
            ["Groq assessment", "Local evidence only"],
            value="Groq assessment",
            label="Review mode",
        )
        with gr.Accordion("Retrieved evidence and assessment status", open=False):
            evidence = gr.Textbox(
                label="Top 3 retrieved chunks and status",
                lines=12,
                max_lines=20,
                interactive=False,
            )
        gr.ChatInterface(
            fn=ui_response_display,
            api_name="ui_response",
            additional_inputs=[mode],
            additional_outputs=[evidence],
            examples=[[example, "Groq assessment"] for example in EXAMPLES],
            title=None,
            description="Start with an exact service name and the planned change. Never enter API keys or other secrets.",
            save_history=False,
            cache_examples=False,
            flagging_mode="never",
            api_visibility="private",
        )
        gr.Markdown(
            "Current freeze/health/dependency verification and persistent team memory are Week 2 work. This demo cannot confirm live operational state."
        )
    return demo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--reindex", action="store_true")
    parser.add_argument(
        "--share",
        action="store_true",
        help="Create a public Gradio tunnel only when explicitly requested; requires CRA2_UI_USER and CRA2_UI_PASSWORD.",
    )
    args = parser.parse_args()
    auth = None
    if args.share:
        user, password = (
            os.environ.get("CRA2_UI_USER"),
            os.environ.get("CRA2_UI_PASSWORD"),
        )
        if not user or not password:
            parser.error(
                "Sharing requires CRA2_UI_USER and CRA2_UI_PASSWORD; do not put credentials on the command line."
            )
        auth = (user, password)
    if args.reindex or not INDEX.exists():
        build_index(HERE / "corpus", INDEX)
    root = HERE.parent
    blocked = [str(root)]
    blocked += [str(p) for p in root.glob(".env.*")]
    selected = os.environ.get("CRA2_ENV_FILE")
    if selected:
        blocked.append(str(Path(selected).expanduser().resolve()))
    build_app().launch(
        server_name="127.0.0.1",
        server_port=args.port,
        share=args.share,
        auth=auth,
        show_error=False,
        blocked_paths=blocked,
        inbrowser=False,
        enable_monitoring=False,
        run_history=False,
        mcp_server=False,
    )


if __name__ == "__main__":
    main()
