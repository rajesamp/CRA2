"""Single-event chat gestures for the local capacity test mount."""
import gradio as gr

from week2.capacity import REVIEW_GROUP


def delivery_js(inputs):
    """Generate one opaque delivery key per gesture before Gradio sends it."""
    return ("(...values) => [{cra2_delivery: crypto.randomUUID().replaceAll('-', ''), "
            f"value: values[0]}}, ...values.slice(1, {inputs})]")


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
