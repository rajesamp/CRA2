"""Slack forms contain public catalog choices, never traces or credentials."""

import html

from cra2.advisor import CATALOG
from week2.help import help_topic

GENERAL = "__general__"
SERVICE_ACTION = "cra_service"
QUESTION_ACTION = "cra_question"
VIEW_CALLBACK = "cra_question_form"


def option(service):
    return {"text": {"type": "plain_text", "text": "General question" if service == GENERAL else service}, "value": service}


def options():
    return [option(service) for service in sorted(CATALOG)] + [option(GENERAL)]


def picker(token):
    return [
        {"type": "section", "text": {"type": "plain_text", "text": "Choose a service to review, or ask a general question."}},
        {"type": "actions", "block_id": "ctx_" + token, "elements": [
            {"type": "static_select", "action_id": SERVICE_ACTION,
             "placeholder": {"type": "plain_text", "text": "Choose a service"}, "options": options()},
            {"type": "button", "action_id": QUESTION_ACTION,
             "text": {"type": "plain_text", "text": "Other question"}, "value": token}]},
    ]


def question_modal(token, service=GENERAL):
    if service != GENERAL and service not in CATALOG:
        raise ValueError("Invalid service")
    return {"type": "modal", "callback_id": VIEW_CALLBACK, "private_metadata": token,
        "title": {"type": "plain_text", "text": "Change risk advisor"},
        "submit": {"type": "plain_text", "text": "Ask"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {"type": "context", "elements": [{"type": "plain_text", "text": "Specific change assessments use Groq. App help runs locally. Never enter credentials."}]},
            {"type": "input", "block_id": "service", "label": {"type": "plain_text", "text": "Service"},
             "element": {"type": "static_select", "action_id": "service", "options": options(), "initial_option": option(service)}},
            {"type": "input", "block_id": "question", "label": {"type": "plain_text", "text": "Your question"},
             "element": {"type": "plain_text_input", "action_id": "question", "multiline": True, "max_length": 3800,
                         "placeholder": {"type": "plain_text", "text": "Describe the change and before/after values, or ask what this app does."}}}]}


def modal_question(view):
    values = view["state"]["values"]
    service = values["service"]["service"]["selected_option"]["value"]
    question = values["question"]["question"]["value"]
    if service != GENERAL and service not in CATALOG:
        raise ValueError("Choose a known service.")
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= 3800:
        raise ValueError("Enter a question of up to 3800 characters.")
    named = [name for name in CATALOG if name in question.lower()]
    if service != GENERAL and named and set(named) != {service}:
        raise ValueError("The selected service must match your question.")
    return question.strip(), service


def with_service(question, service):
    # General app help must not become an assessment merely because a service
    # was selected. Other service questions get explicit, bounded context.
    if service not in (None, GENERAL) and service not in CATALOG:
        raise ValueError("Invalid service")
    if service in (None, GENERAL) or service in question.lower() or help_topic(question, None, CATALOG):
        return question
    return service + ": " + question


def answer_payload(answer):
    # Plain-text blocks and escaped notification text avoid Slack mention/link
    # injection. No model output is interpreted as Block Kit or destinations.
    text = answer[:2900].replace("**", "")
    return {"text": html.escape(text, quote=False), "blocks": [
        {"type": "section", "text": {"type": "plain_text", "text": text}}]}
