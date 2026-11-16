"""Owner-only Cloud Run entrypoint. This does not enable multi-user deployment."""
import os
from pathlib import Path
import re

from fastapi import FastAPI, Request
import gradio as gr
import uvicorn

from week2.app import build_app
from week2.abuse import AbuseGate
from week2.iap import IAPMiddleware, IAPSettings, IAPVerifier, Principal
from week2.memory import MemoryStore
from week2.owner_audit import OwnerAuditStore


def request_identity(request):
    # Gradio supplies username from our auth_dependency, never browser form data.
    value = request.username if request is not None else None
    if not isinstance(value, str) or not re.fullmatch(r"iap:[0-9a-f]{64}", value):
        raise ValueError("Verified identity unavailable")
    return value


def create_app(*, settings=None, verifier=None, memory_store=None, abuse_gate=None):
    settings = settings or IAPSettings(os.environ.get("CRA2_IAP_AUDIENCE", ""),
                                      os.environ.get("CRA2_OWNER_EMAIL", ""))
    verifier = verifier or IAPVerifier(settings)
    if verifier.settings != settings:
        raise ValueError("Identity verifier configuration mismatch")
    api = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    def authenticated_user(request: Request):
        principal = getattr(request.state, "cra2_principal", None)
        return principal.key if isinstance(principal, Principal) else None

    # Ephemeral storage is explicit for this integration milestone. Durable
    # storage and audit release gates must pass before deploying the demo.
    store = memory_store or MemoryStore("/tmp/cra2-state/team-memory.sqlite3")
    gate = abuse_gate or AbuseGate(store=OwnerAuditStore("/tmp/cra2-owner/audit.sqlite3"))
    demo = build_app(memory_store=store, abuse_gate=gate, identity_resolver=request_identity)
    blocked = [str(Path(__file__).resolve().parents[1])]
    if os.environ.get("CRA2_ENV_FILE"):
        blocked.append(str(Path(os.environ["CRA2_ENV_FILE"]).expanduser().resolve()))
    gr.mount_gradio_app(api, demo, path="/", auth_dependency=authenticated_user,
        blocked_paths=blocked, show_error=False, enable_monitoring=False, mcp_server=False,
        run_history=False, footer_links=[], max_file_size="1mb", ssr_mode=False,
        app_kwargs={"docs_url": None, "redoc_url": None, "openapi_url": None})
    return IAPMiddleware(api, verifier)


def main():
    try:
        port = int(os.environ.get("PORT", "8080"))
    except ValueError:
        raise ValueError("Invalid runtime port") from None
    if not 1 <= port <= 65535:
        raise ValueError("Invalid runtime port")
    os.environ["FORWARDED_ALLOW_IPS"] = ""
    uvicorn.run(create_app(), host="0.0.0.0", port=port, workers=1,
                proxy_headers=False, access_log=False, log_level="warning")


if __name__ == "__main__":
    main()
