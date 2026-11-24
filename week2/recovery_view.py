"""Deliver only the current recovery gesture to this tab's report element."""
import re

HINT = "Run the analysis to inspect incident sources and recovery gaps."
VIEW = '<div aria-live="polite" class="recovery-current">' + HINT + '</div>'

# The browser owns the active form revision. Clearing it on every edit also
# invalidates an edit followed by a return to the same text.
HEAD = """<script>
(() => {
  let current = null;
  const view = () => document.querySelector("#recovery-report .recovery-current");
  function clear() {
    current = null;
    const target = view();
    if (target) target.textContent = "Run the analysis for the current change.";
  }
  // Invalidate synchronously, before an outstanding Gradio response can
  // run. Text fields dispatch input, while dropdowns also support menu and
  // keyboard selection. Restrict these listeners to the seven review fields.
  function edited(event) {
    const field = ".cra2-recovery-field";
    if (event.type === "pointerdown") {
      // A dropdown can remove its option before click bubbles. Some menus
      // are portaled outside the field while their combobox retains focus.
      if (!event.target.closest?.('[role="option"], option')) return;
      if (!event.target.closest(field) && !document.activeElement?.closest(field)) return;
    } else if (!event.target.closest?.(field)) return;
    if (event.type === "keydown" && !(event.key === "Enter" &&
        event.target.matches('[role="combobox"][aria-expanded="true"]'))) return;
    clear();
  }
  for (const type of ["input", "change", "pointerdown", "keydown"]) {
    document.addEventListener(type, edited, true);
  }
  window.addEventListener("pagehide", clear);
  function begin() {
    clear();
    current = crypto.randomUUID().replaceAll("-", "");
    return current;
  }
  function deliver(value) {
    if (!current || typeof value !== "string") return;
    const prefix = "<!--cra2-view:" + current + "-->";
    if (value.startsWith(prefix) && view()) {
      current = null;
      view().innerHTML = value.slice(prefix.length);
    }
  }
  window.cra2Recovery = {clear, begin, deliver};
  // The ordinary Gradio mount accepts a scalar dropdown. Move its view
  // receipt to a header on this request only. The capacity mount already
  // transports the receipt with its existing idempotent delivery envelope.
  const send = window.fetch.bind(window);
  window.fetch = async (resource, options) => {
    const url = new URL(resource instanceof Request ? resource.url : resource, location.href);
    if (url.origin === location.origin && url.pathname.endsWith("/gradio_api/queue/join") &&
        typeof options?.body === "string") {
      const body = JSON.parse(options.body);
      const first = body.data?.[0];
      if (first && typeof first.cra2_view === "string") {
        body.data[0] = first.value;
        const headers = new Headers(options.headers);
        headers.set("X-Cra2-View", first.cra2_view);
        options = {...options, body: JSON.stringify(body), headers};
      }
    }
    const response = await send(resource, options);
    if (url.origin === location.origin && url.pathname.startsWith("/gradio_api/") &&
        (response.status === 401 || response.status === 403)) clear();
    return response;
  };
})();
</script>"""


def submit_js(capacity):
    key = "cra2_delivery" if capacity else "cra2_view"
    return ("(...values) => { const notice = document.getElementById('cra2-capacity-message'); "
            "if (notice) notice.hidden = true; "
            f"return [{{{key}: window.cra2Recovery.begin(), value: values[0]}}, ...values.slice(1, 8)]; }}")


def delivery(html, request):
    state = getattr(getattr(request, "request", None), "state", None)
    receipt = getattr(state, "cra2_delivery_id", None)
    if not isinstance(receipt, str):
        receipt = (getattr(request, "headers", None) or {}).get("x-cra2-view")
    if isinstance(receipt, str) and re.fullmatch("[a-f0-9]{32}", receipt):
        return f"<!--cra2-view:{receipt}-->" + html
    return html
