"""Week 1 adapter regressions with fake SDK replies and an in-memory HTTP transport."""

import json
import socket
from copy import deepcopy
from secrets import token_hex
from types import SimpleNamespace

import groq
import httpx
import pytest

from cra2 import config, system2
from week1 import provider

ORIGINAL_CLIENT = system2.client
PAYLOAD = {
    "change": {
        "service": "checkout-service",
        "summary": "Change payment timeout from 4 seconds to 400 milliseconds.",
    },
    "evidence_keys": ["pm-cx101:chunk-1", "team:checkout-service.high_risk"],
    "incidents": [
        {
            "chunk_id": "pm-cx101:chunk-1",
            "text": "Historical charges without orders followed a shorter timeout.",
        }
    ],
    "settings": {
        "effective": {"high_risk": False},
        "sources": {"high_risk": "team:checkout-service.high_risk"},
    },
}
ANSWER = {
    "ratings": {
        name: "low"
        for name in (
            "deploy_order",
            "rollback",
            "config_drift",
            "dependencies",
            "monitoring",
        )
    },
    "comments": [
        {
            "tag": "history",
            "severity": "low",
            "text": "How will the proposed timeout be compared with historical payment latency?",
            "evidence": ["pm-cx101:chunk-1"],
        },
        {
            "tag": "monitoring",
            "severity": "low",
            "text": "How will charges without orders be detected during review?",
            "evidence": ["pm-cx101:chunk-1"],
        },
        {
            "tag": "rollback",
            "severity": "low",
            "text": "What is the plan for restoring the previous timeout?",
            "evidence": ["pm-cx101:chunk-1"],
        },
    ],
}


def response(answer=None, *, usage=True):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(
                    content=json.dumps(ANSWER if answer is None else answer),
                    refusal=None,
                ),
            )
        ],
        model="test-model",
        system_fingerprint="test-fingerprint",
        usage=SimpleNamespace(prompt_tokens=120, completion_tokens=40, total_time=0.025)
        if usage
        else None,
    )


@pytest.fixture(autouse=True)
def offline_credentials(monkeypatch):
    monkeypatch.delenv("CRA2_ENV_FILE", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", token_hex(24))
    monkeypatch.setattr(
        system2,
        "client",
        lambda: pytest.fail("each test must supply a fake SDK client"),
    )
    monkeypatch.setattr(
        socket.socket,
        "connect",
        lambda *_a, **_k: pytest.fail("provider tests must not use the network"),
    )
    monkeypatch.setattr(
        socket.socket,
        "connect_ex",
        lambda *_a, **_k: pytest.fail("provider tests must not use the network"),
    )


@pytest.fixture
def sdk(monkeypatch):
    calls = []
    fake = SimpleNamespace(api_key=token_hex(24), response=response(), failure=None)

    def create(**kwargs):
        calls.append(kwargs)
        if fake.failure is not None:
            raise fake.failure
        return fake.response

    fake.chat = SimpleNamespace(completions=SimpleNamespace(create=create))
    fake.calls = calls
    monkeypatch.setattr(system2, "client", lambda: fake)
    return fake


def test_request_appends_week1_contract_without_changing_core_prompt_or_cache(sdk):
    base_prompt = system2.PROMPT
    cache_before = dict(system2._RESULTS)
    first = provider.assess(PAYLOAD, {})
    second = provider.assess(PAYLOAD, {})
    assert len(sdk.calls) == 2
    for result in (first, second):
        assert result["cache_hit"] is False and result["request_attempted"] is True
        assert result["tokens"] == [120, 40] and result["groq_ms"] == 25
        assert result["out"] == ANSWER
        assert "score" not in result
    sent = sdk.calls[0]
    prompt = sent["messages"][0]["content"]
    assert prompt.startswith(base_prompt + "\n\n")
    assert "Additional Week 1 historical-evidence contract" in prompt
    assert (
        "verification question" in prompt and "Do not embellish consequences" in prompt
    )
    assert "A policy key cannot support an incident claim" in prompt
    assert json.loads(sent["messages"][1]["content"]) == PAYLOAD
    assert system2.PROMPT == base_prompt and dict(system2._RESULTS) == cache_before


def test_request_uses_configured_sampling_bounds_and_provider_schema(sdk):
    provider.assess(PAYLOAD, {})
    sent = sdk.calls[0]
    assert sent["model"] == config.MODEL
    assert sent["temperature"] == config.TEMPERATURE and sent["seed"] == config.SEED
    assert sent["max_completion_tokens"] == config.MAX_TOKENS
    assert sent["timeout"] == config.TIMEOUT_S
    assert all(sent[key] == value for key, value in config.REASONING.items())
    contract = sent["response_format"]["json_schema"]
    assert contract["strict"] is True and contract["name"] == "assessment"
    assert "uniqueItems" not in json.dumps(contract["schema"])
    assert (
        system2.SCHEMA["properties"]["comments"]["items"]["properties"]["evidence"][
            "uniqueItems"
        ]
        is True
    )


def test_local_full_schema_still_rejects_duplicate_evidence_with_usage(sdk):
    answer = deepcopy(ANSWER)
    answer["comments"][0]["evidence"] *= 2
    sdk.response = response(answer)
    with pytest.raises(system2.System2Unavailable) as caught:
        provider.assess(PAYLOAD, {})
    assert caught.value.request_attempted is True
    assert caught.value.tokens == [120, 40] and caught.value.groq_ms == 25
    assert caught.value.__context__ is None and caught.value.__cause__ is None


@pytest.mark.parametrize("location", ["payload", "prompt", "model"])
def test_configured_credential_is_rejected_before_client_initialization(
    monkeypatch, location
):
    sentinel = token_hex(24)
    monkeypatch.setenv("GROQ_API_KEY", sentinel)
    payload = deepcopy(PAYLOAD)
    if location == "payload":
        payload["incidents"][0]["text"] += sentinel
    elif location == "prompt":
        monkeypatch.setattr(provider, "PROMPT", provider.PROMPT + sentinel)
    else:
        monkeypatch.setattr(config, "MODEL", sentinel)
    with pytest.raises(system2.System2Unavailable) as caught:
        provider.assess(payload, {})
    assert caught.value.request_attempted is False
    assert caught.value.tokens is None
    assert sentinel not in str(caught.value)
    assert caught.value.__context__ is None


def test_sdk_held_credential_is_rejected_before_request(sdk):
    payload = deepcopy(PAYLOAD)
    payload["settings"]["team"] = sdk.api_key
    with pytest.raises(system2.System2Unavailable) as caught:
        provider.assess(payload, {})
    assert not sdk.calls and caught.value.request_attempted is False
    assert sdk.api_key not in str(caught.value)


def test_returned_credential_is_rejected_with_received_usage(sdk):
    answer = deepcopy(ANSWER)
    answer["comments"][0]["text"] += sdk.api_key
    sdk.response = response(answer)
    with pytest.raises(system2.System2Unavailable) as caught:
        provider.assess(PAYLOAD, {})
    assert len(sdk.calls) == 1 and caught.value.request_attempted is True
    assert caught.value.tokens == [120, 40] and caught.value.groq_ms == 25
    assert sdk.api_key not in str(caught.value)
    assert caught.value.__context__ is None


def test_provider_error_is_generic_and_has_no_exception_chain(sdk):
    sentinel = token_hex(24)
    sdk.failure = groq.GroqError("Transport diagnostics " + sentinel)
    with pytest.raises(system2.System2Unavailable) as caught:
        provider.assess(PAYLOAD, {})
    assert len(sdk.calls) == 1 and caught.value.request_attempted is True
    assert caught.value.tokens is None and caught.value.groq_ms is None
    assert sentinel not in str(caught.value)
    assert caught.value.__context__ is None and caught.value.__cause__ is None


def test_missing_client_does_not_claim_provider_attempt(monkeypatch):
    sentinel = token_hex(24)

    def missing():
        raise groq.GroqError(sentinel)

    monkeypatch.setattr(system2, "client", missing)
    with pytest.raises(system2.System2Unavailable) as caught:
        provider.assess(PAYLOAD, {})
    assert caught.value.request_attempted is False
    assert caught.value.tokens is None and caught.value.groq_ms is None
    assert sentinel not in str(caught.value)
    assert caught.value.__context__ is None and caught.value.__cause__ is None


def test_missing_usage_is_unknown_not_zero(sdk):
    sdk.response = response(usage=False)
    result = provider.assess(PAYLOAD, {})
    assert result["tokens"] is None and result["groq_ms"] is None
    assert result["request_attempted"] is True and result["cache_hit"] is False


def test_protected_sdk_pins_groq_origin_and_disables_retries(monkeypatch):
    requests = []
    real_factory = groq.Groq
    monkeypatch.setenv("GROQ_BASE_URL", "https://untrusted.invalid")

    def handler(request):
        requests.append(request)
        return httpx.Response(
            503,
            json={
                "error": {"message": "temporary mock failure", "type": "server_error"}
            },
        )

    clients = []

    def factory(**kwargs):
        assert kwargs["base_url"] == "https://api.groq.com"
        assert kwargs["max_retries"] == 0
        client = real_factory(
            api_key=token_hex(24),
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            **kwargs,
        )
        clients.append(client)
        return client

    ORIGINAL_CLIENT.cache_clear()
    monkeypatch.setattr(system2, "client", ORIGINAL_CLIENT)
    monkeypatch.setattr(groq, "Groq", factory)
    try:
        with pytest.raises(system2.System2Unavailable) as caught:
            provider.assess(PAYLOAD, {})
        assert caught.value.request_attempted is True
        assert len(requests) == 1
        assert str(requests[0].url) == "https://api.groq.com/openai/v1/chat/completions"
        assert requests[0].headers["authorization"].startswith("Bearer ")
    finally:
        for client in clients:
            client.close()
        ORIGINAL_CLIENT.cache_clear()


def test_week1_filter_keeps_questions_and_discards_declarative_claims(sdk):
    answer = deepcopy(ANSWER)
    answer["comments"][0]["text"] = (
        "Historical charges without orders prove financial loss."
    )
    answer["comments"][1]["text"] += "   "
    sdk.response = response(answer)
    result = provider.assess(PAYLOAD, {})
    assert result["out"]["comments"] == answer["comments"][1:]
    assert result["tokens"] == [120, 40] and result["request_attempted"] is True
    assert "financial loss" not in str(result)


def test_no_usable_questions_cannot_produce_chat_risk_indication(sdk):
    from week1 import chat

    answer = deepcopy(ANSWER)
    for comment in answer["comments"]:
        comment["text"] = "This is a declarative claim about historical impact."
    sdk.response = response(answer)
    source = {
        "chunk_id": "pm-cx101:chunk-1",
        "doc_id": "pm-cx101",
        "title": "Historical timeout incident",
        "source": "week1/corpus/pm-cx101.md",
        "kind": "postmortem",
        "score": 0.9,
        "text": "Historical charges without orders followed a shorter timeout.",
    }
    text, trace = chat.respond(
        "Change checkout-service timeout from 4 seconds to 400 milliseconds.",
        retriever=lambda *_a, **_k: [source],
    )
    assert len(sdk.calls) == 1
    assert trace["status"] == "insufficient_evidence"
    assert trace["request_attempted"] is True and trace["tokens"] == [120, 40]
    assert "**Risk indication:" not in text
    assert "no usable evidence-linked assessment" in text
