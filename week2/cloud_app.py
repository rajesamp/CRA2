"""IAP-protected Cloud Run entrypoint; additional accounts require explicit configuration."""
import os
from pathlib import Path
import re

from fastapi import FastAPI, Request
import gradio as gr
import uvicorn

from week2.app import build_app
from week2.abuse import AbuseGate
from week2.capacity import LocalCapacity
from week2.capacity_chat import CAPACITY_HEAD
from week2.cloud_storage import CloudStores
from week2.iap import IAPMiddleware, IAPSettings, IAPVerifier, Principal
from week2.presence import Presence, principal_from_request
from week2.session_boundary import SessionBoundary


# Preserve an idempotency key on transport redelivery of the same Gradio POST.
REVIEW_HEAD = """<script>
(() => {
  const send = window.fetch.bind(window);
  const keys = new WeakMap();
  window.fetch = (resource, options) => {
    const request = resource instanceof Request ? resource : null;
    const url = new URL(request?.url || resource, location.href);
    const method = options?.method || request?.method || "GET";
    if (url.origin !== location.origin || method.toUpperCase() !== "POST" ||
        !url.pathname.startsWith("/gradio_api/")) return send(resource, options);
    const headers = new Headers(options?.headers || request?.headers);
    const gesture = options || request;
    if (gesture && !headers.has("Idempotency-Key")) {
      if (!keys.has(gesture)) keys.set(gesture, crypto.randomUUID().replaceAll("-", ""));
      headers.set("Idempotency-Key", keys.get(gesture));
    }
    return send(resource, {...options, headers});
  };
})();
</script>"""


def request_identity(request):
    # Gradio supplies username from our auth_dependency, never browser form data.
    value = request.username if request is not None else None
    if not isinstance(value, str) or not re.fullmatch(r"iap:[0-9a-f]{64}", value):
        raise ValueError("Verified identity unavailable")
    return value


def create_app(*, settings=None, verifier=None, stores=None, local_capacity_path=None):
    settings = settings or IAPSettings(os.environ.get("CRA2_IAP_AUDIENCE", ""),
                                      os.environ.get("CRA2_OWNER_EMAIL", ""),
                                      tuple(value.strip() for value in os.environ.get("CRA2_ALLOWED_EMAILS", "").split(",") if value.strip()))
    verifier = verifier or IAPVerifier(settings)
    if verifier.settings != settings:
        raise ValueError("Identity verifier configuration mismatch")
    api = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    def authenticated_user(request: Request):
        principal = getattr(request.state, "cra2_principal", None)
        return principal.key if isinstance(principal, Principal) else None

    stores = CloudStores.from_env() if stores is None else stores
    capacity = LocalCapacity(local_capacity_path) if local_capacity_path is not None else None
    gate = AbuseGate(store=stores.audit, cooldowns=capacity)
    presence = Presence()
    demo = build_app(memory_resolver=stores.memory_for, telemetry_store=stores.telemetry,
                     abuse_gate=gate, identity_resolver=request_identity, local_capacity=capacity,
                     identity_view=lambda request: presence.view(principal_from_request(request)))
    blocked = [str(Path(__file__).resolve().parents[1])]
    if os.environ.get("CRA2_ENV_FILE"):
        blocked.append(str(Path(os.environ["CRA2_ENV_FILE"]).expanduser().resolve()))
    gr.mount_gradio_app(api, demo, path="/", auth_dependency=authenticated_user,
        head=CAPACITY_HEAD if capacity is not None else REVIEW_HEAD,
        theme=gr.themes.Soft(primary_hue="teal", neutral_hue="slate"),
        blocked_paths=blocked, show_error=False, enable_monitoring=False, mcp_server=False,
        run_history=False, footer_links=[], max_file_size="1mb", ssr_mode=False,
        app_kwargs={"docs_url": None, "redoc_url": None, "openapi_url": None})
    return IAPMiddleware(SessionBoundary(api, demo, presence, capacity), verifier)


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
