"""Single-event chat gestures for the local capacity test mount."""
import gradio as gr

from week2.capacity import REVIEW_GROUP


# The pinned Gradio client replaces every queue-join 503 with a generic toast.
# Keep the server's authoritative retry hint available to the signed-in user.
CAPACITY_HEAD = """<script>
(() => {
  if (window.cra2CapacityFeedback) return;
  window.cra2CapacityFeedback = true;
  const original = window.fetch.bind(window);
  window.fetch = async function(resource, options) {
    const target = new URL(resource instanceof Request ? resource.url : resource, location.href);
    const method = options?.method || resource.method || "GET";
    const signal = options?.signal || resource.signal;
    const isDataStream = target.origin === location.origin && method.toUpperCase() === "GET" &&
      target.pathname === "/gradio_api/queue/data";
    const until = performance.now() + 15000;
    let response;
    // Retry only the read of this session's existing result stream. A submitted
    // review is never retransmitted here. Stop on tab close or grace expiry.
    for (let attempt = 0; ; attempt++) {
      try {
        response = await original(resource, options);
      } catch (error) {
        if (!isDataStream || signal?.aborted || attempt >= 3 || performance.now() + 1000 >= until) throw error;
        await new Promise(resolve => setTimeout(resolve, 1000));
        continue;
      }
      if (!isDataStream || ![429, 503].includes(response.status) || signal?.aborted || attempt >= 3) break;
      const wait = Number(response.headers.get("Retry-After"));
      if (!Number.isInteger(wait) || wait < 1 || performance.now() + wait*1000 >= until) break;
      await response.body?.cancel();
      await new Promise(resolve => setTimeout(resolve, wait*1000));
    }
    if (response.status !== 429 && response.status !== 503) return response;
    const url = new URL(response.url || target);
    const hint = Number(response.headers.get("Retry-After"));
    if (url.origin !== location.origin || !url.pathname.startsWith("/gradio_api/") ||
        !Number.isInteger(hint) || hint < 1 || hint > 60) return response;
    const notice = document.getElementById("cra2-capacity-message");
    if (notice) {
      const body = await response.clone().json().catch(() => ({}));
      notice.textContent = typeof body.detail === "string" ? body.detail :
        "Review capacity is busy. Retry in " + hint + " seconds.";
      notice.hidden = false;
    }
    return response;
  };
})();
</script>"""


def delivery_js(inputs):
    """Generate one opaque delivery key per gesture before Gradio sends it."""
    return ("(...values) => {const notice = document.getElementById('cra2-capacity-message'); "
            "if (notice) notice.hidden = true; return [{cra2_delivery: crypto.randomUUID().replaceAll('-', ''), "
            f"value: values[0]}}, ...values.slice(1, {inputs})];}}")


class CapacityChat(gr.ChatInterface):
    """Keep the draft intact until the admitted callback successfully returns."""

    def _setup_events(self):
        def deliver(message, history, mode, session, traces, activity, request):
            answer, *extra = self.fn(message, list(history), mode, session, traces, request, activity)
            updated = self._append_message_to_history(message, history, "user")
            updated = self._append_message_to_history(answer, updated, "assistant")
            return "", updated, updated, *extra

        def submit(message, history, mode, session, traces, activity, request: gr.Request):
            return deliver(message, history, mode, session, traces, activity, request)

        def retry(history, mode, session, traces, activity, request: gr.Request):
            previous, message = self._pop_last_user_message(history)
            return deliver(message, previous, mode, session, traces, activity, request)

        def choose(history, mode, session, traces, activity, option: gr.SelectData, request: gr.Request):
            return deliver(option.value, history, mode, session, traces, activity, request)

        inputs = [self.chatbot, *self.additional_inputs]
        outputs = [self.textbox, self.chatbot, self.chatbot_state, *self.additional_outputs]
        # Gradio clears visible output components on a failed queue join. Keep
        # the draft and conversation out of the submission's failure path.
        pending = gr.State()
        events = dict(outputs=pending, concurrency_limit=1, concurrency_id=REVIEW_GROUP,
                      api_visibility="private", show_progress="minimal")
        submitted = self.textbox.submit(submit, [self.textbox, *inputs], api_name="submit_review",
                                        js=delivery_js(1 + len(inputs)), **events)
        retried = self.chatbot.retry(retry, inputs, api_name="retry_review", js=delivery_js(len(inputs)), **events)
        chosen = self.chatbot.option_select(choose, inputs, api_name="choose_review", js=delivery_js(len(inputs)), **events)
        def publish(result):
            return result
        for event in (submitted, retried, chosen):
            event.success(publish, pending, outputs, queue=False, api_visibility="private")
        self.fake_api_btn.click(self._api_wrapper(self.fn, self._submit_fn),
            [self.textbox, self.chatbot_state, *self.additional_inputs],
            [self.api_response, self.chatbot_state, *self.additional_outputs],
            api_name=self.api_name, api_visibility="private", postprocess=False,
            concurrency_limit=1, concurrency_id=REVIEW_GROUP)

        # Queue cancellation must stay reachable even while review capacity is full.
        cancel = gr.Button("Cancel review", size="sm")
        cancel.click(None, cancels=[submitted, retried, chosen], queue=False, api_visibility="private")
        self.chatbot.undo(self._pop_last_user_message, [self.chatbot], [self.chatbot, self.textbox],
                          queue=False, api_visibility="private").success(
            lambda history: history, self.chatbot, self.chatbot_state, queue=False, api_visibility="private")
        self.chatbot.clear(lambda: [], None, self.chatbot_state, queue=False, api_visibility="private")
