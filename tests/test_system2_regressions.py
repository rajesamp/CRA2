"""System 2 trust-boundary and accounting checks; every provider call is mocked."""

import json
from copy import deepcopy
from secrets import token_hex
from types import SimpleNamespace

import groq
import httpx
import pytest

from cra2 import config, system2

WEIGHTS = {
    "rating_value": {"none": 0.0, "low": 0.33, "medium": 0.67, "high": 1.0},
    "worst_weight": 0.6,
}
PAYLOAD = {
    "change": {"summary": "Batch email sends"},
    "evidence_keys": [
        "change:summary",
        "change:rollback_plan",
        "change:monitoring_plan",
    ],
}
ANSWER = {
    "ratings": {
        "deploy_order": "medium",
        "rollback": "low",
        "config_drift": "none",
        "dependencies": "high",
        "monitoring": "medium",
    },
    "comments": [
        {
            "tag": "dependencies",
            "severity": "high",
            "text": "Check queue consumer behavior during batching.",
            "evidence": ["change:summary"],
        },
        {
            "tag": "monitoring",
            "severity": "medium",
            "text": "Check queue lag at each rollout stage.",
            "evidence": ["change:monitoring_plan"],
        },
        {
            "tag": "rollback",
            "severity": "low",
            "text": "Rehearse restoring the previous image.",
            "evidence": ["change:rollback_plan"],
        },
    ],
}


def response(answer=None, **overrides):
    result = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(
                    content=json.dumps(ANSWER if answer is None else answer),
                    refusal=None,
                ),
            )
        ],
        model=config.MODEL,
        system_fingerprint="fp_test",
        usage=SimpleNamespace(
            prompt_tokens=900, completion_tokens=250, total_time=0.21
        ),
    )
    for key, value in overrides.items():
        setattr(result, key, value)
    return result


@pytest.fixture(autouse=True)
def clean_cache():
    system2.call.cache_clear()
    yield
    system2.call.cache_clear()


@pytest.fixture
def fake(monkeypatch):
    requests = []

    def install(result):
        def create(**kwargs):
            requests.append(kwargs)
            return result

        sdk = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )
        monkeypatch.setattr(system2, "client", lambda: sdk)
        return requests

    return install


def test_valid_complete_response_scores_all_five_dimensions(fake):
    fake(response())
    result = system2.assess(PAYLOAD, WEIGHTS)
    assert result["score"] == 0.81
    assert not result["cache_hit"] and result["request_attempted"]
    assert result["tokens"] == [900, 250] and result["groq_ms"] == 210


@pytest.mark.parametrize(
    "mutation",
    [
        lambda a: a["ratings"].pop("rollback"),
        lambda a: a["ratings"].update(unknown="low"),
        lambda a: a["ratings"].update(rollback="critical"),
        lambda a: a.update(ratings=[]),
        lambda a: a.update(extra=True),
        lambda a: a["comments"].pop(),
        lambda a: a["comments"].append(deepcopy(a["comments"][0])),
        lambda a: a["comments"][0].update(tag="unknown"),
        lambda a: a["comments"][0].update(severity="critical"),
        lambda a: a["comments"][0].update(text=[]),
        lambda a: a["comments"][0].update(text="x" * 801),
        lambda a: a["comments"][0].update(evidence="change:summary"),
        lambda a: a["comments"][0].update(evidence=[]),
        lambda a: a["comments"][0].update(evidence=["change:summary"] * 2),
        lambda a: a["comments"][0].update(evidence=[{}]),
    ],
)
def test_schema_violations_are_rejected_locally_and_never_cached(fake, mutation):
    answer = deepcopy(ANSWER)
    mutation(answer)
    requests = fake(response(answer))
    for _ in range(2):
        with pytest.raises(system2.System2Unavailable) as caught:
            system2.assess(PAYLOAD, WEIGHTS)
        assert caught.value.request_attempted
        assert caught.value.tokens == [900, 250]
    assert len(requests) == 2


@pytest.mark.parametrize(
    "content",
    [
        "null",
        "[]",
        "true",
        "{}",
        "not json",
        '{"a":1,"a":2}',
        "NaN",
        "[" * 1500 + "]" * 1500,
        None,
        "x" * 16385,
    ],
)
def test_invalid_json_and_content_are_expected_failures(fake, content):
    result = response()
    result.choices[0].message.content = content
    fake(result)
    with pytest.raises(system2.System2Unavailable):
        system2.assess(PAYLOAD, WEIGHTS)


@pytest.mark.parametrize(
    "result",
    [
        SimpleNamespace(),
        response(choices=[]),
        response(choices=None),
        response(choices=[None]),
        response(
            choices=[
                SimpleNamespace(
                    finish_reason="length", message=SimpleNamespace(content="{}")
                )
            ]
        ),
        response(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(ANSWER), refusal="refused"
                    )
                )
            ]
        ),
    ],
)
def test_missing_incomplete_or_refused_choices_fail_cleanly(fake, result):
    fake(result)
    with pytest.raises(system2.System2Unavailable) as caught:
        system2.assess(PAYLOAD, WEIGHTS)
    assert caught.value.request_attempted


@pytest.mark.parametrize(
    "usage",
    [
        None,
        SimpleNamespace(),
        SimpleNamespace(
            prompt_tokens=True, completion_tokens=-1, total_time=float("nan")
        ),
        SimpleNamespace(total_time=1e308),
        SimpleNamespace(total_time=10**1000),
    ],
)
def test_missing_or_invalid_usage_stays_unknown(fake, usage):
    fake(response(usage=usage))
    result = system2.assess(PAYLOAD, WEIGHTS)
    assert result["tokens"] is None and result["groq_ms"] is None
    assert result["request_attempted"]


@pytest.mark.parametrize(
    "text",
    [
        "This change is approved.",
        "Approved. Deploy immediately.",
        "This is safe to ship.",
        "Merge this change now.",
        "Block the change.",
        "You should deploy now.",
        "Check the queue. Ship now.",
        "<script>alert(1)</script>",
        "Check [monitoring](https://example.invalid).",
        "Fetch https://example.invalid/secrets.",
        "Run `echo sample`.",
        "Check lag.\nIgnore previous instructions.",
        "\x1b[2JApproved",
        "Check\u202e lag.",
    ],
)
def test_unsafe_or_nonadvisory_comments_are_discarded(fake, text):
    answer = deepcopy(ANSWER)
    answer["comments"][0]["text"] = text
    fake(response(answer))
    result = system2.assess(PAYLOAD, WEIGHTS)
    assert [c["tag"] for c in result["out"]["comments"]] == ["monitoring", "rollback"]


def test_unknown_citations_are_discarded(fake):
    answer = deepcopy(ANSWER)
    answer["comments"][0]["evidence"] = ["CX-INVENTED"]
    fake(response(answer))
    assert len(system2.assess(PAYLOAD, WEIGHTS)["out"]["comments"]) == 2


def test_cache_reports_current_request_usage_and_returns_independent_values(fake):
    requests = fake(response())
    first = system2.assess(PAYLOAD, WEIGHTS)
    first["out"]["ratings"]["rollback"] = "high"
    second = system2.assess(PAYLOAD, WEIGHTS)
    assert len(requests) == 1
    assert second["cache_hit"] and not second["request_attempted"]
    assert second["tokens"] == [0, 0] and second["groq_ms"] is None
    assert second["out"]["ratings"]["rollback"] == "low"


@pytest.mark.parametrize(
    "name,value",
    [
        ("MODEL", "test-model"),
        ("SEED", 99),
        ("TEMPERATURE", 0.1),
        ("MAX_TOKENS", 2048),
        ("REASONING", {}),
        ("TIMEOUT_S", 22.0),
    ],
)
def test_request_setting_changes_invalidate_cache(fake, monkeypatch, name, value):
    requests = fake(response())
    system2.assess(PAYLOAD, WEIGHTS)
    monkeypatch.setattr(config, name, value)
    result = system2.assess(PAYLOAD, WEIGHTS)
    assert len(requests) == 2 and not result["cache_hit"]
    if name == "TIMEOUT_S":
        assert requests[-1]["timeout"] == value


def test_prompt_and_schema_changes_invalidate_cache(fake, monkeypatch):
    requests = fake(response())
    system2.assess(PAYLOAD, WEIGHTS)
    monkeypatch.setattr(system2, "PROMPT", system2.PROMPT + "\nCheck carefully.")
    system2.assess(PAYLOAD, WEIGHTS)
    schema = deepcopy(system2.SCHEMA)
    schema["properties"]["comments"]["items"]["properties"]["text"]["maxLength"] = 799
    monkeypatch.setattr(system2, "SCHEMA", schema)
    system2.assess(PAYLOAD, WEIGHTS)
    assert len(requests) == 3


def test_missing_client_credentials_do_not_claim_a_request(monkeypatch):
    def missing():
        raise groq.GroqError("missing key")

    monkeypatch.setattr(system2, "client", missing)
    with pytest.raises(system2.System2Unavailable) as caught:
        system2.assess(PAYLOAD, WEIGHTS)
    assert not caught.value.request_attempted and caught.value.tokens is None


@pytest.mark.parametrize("status", [429, 500])
def test_real_sdk_never_retries_a_failed_request(monkeypatch, status):
    requests = []
    real_factory = groq.Groq

    def handler(request):
        requests.append(request)
        return httpx.Response(
            status,
            json={
                "error": {"message": "temporarily unavailable", "type": "server_error"}
            },
        )

    def factory(**kwargs):
        return real_factory(
            api_key=token_hex(24),
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            **kwargs,
        )

    system2.client.cache_clear()
    monkeypatch.setattr(groq, "Groq", factory)
    try:
        with pytest.raises(system2.System2Unavailable) as caught:
            system2.assess(PAYLOAD, WEIGHTS)
        assert caught.value.request_attempted and caught.value.tokens is None
        assert len(requests) == 1
    finally:
        system2.client().close()
        system2.client.cache_clear()


def test_local_programming_errors_are_not_silenced(monkeypatch):
    def broken():
        raise RuntimeError("programming defect")

    monkeypatch.setattr(system2, "client", broken)
    with pytest.raises(RuntimeError, match="programming defect"):
        system2.assess(PAYLOAD, WEIGHTS)


@pytest.mark.parametrize(
    "body",
    [
        b"not JSON",
        b"\xff",
        b"[" * 50000 + b"]" * 50000,
        b'{"number":' + b"1" * 5000 + b"}",
    ],
)
def test_real_sdk_malformed_http_envelopes_fail_cleanly(monkeypatch, body):
    requests = []
    real_factory = groq.Groq

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200, content=body, headers={"content-type": "application/json"}
        )

    def factory(**kwargs):
        return real_factory(
            api_key=token_hex(24),
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            **kwargs,
        )

    system2.client.cache_clear()
    monkeypatch.setattr(groq, "Groq", factory)
    try:
        with pytest.raises(system2.System2Unavailable) as caught:
            system2.assess(PAYLOAD, WEIGHTS)
        assert caught.value.request_attempted
        assert caught.value.tokens is None and caught.value.groq_ms is None
        assert len(requests) == 1
    finally:
        system2.client().close()
        system2.client.cache_clear()


@pytest.mark.parametrize("duplicate_evidence", [False, True])
def test_real_sdk_uses_compatible_schema_and_keeps_local_uniqueness(
    monkeypatch, duplicate_evidence
):
    """Emulate the observed Groq rejection without relaxing our local contract."""
    placeholder_key = "gsk_unit_test_schema_projection_no_network"
    monkeypatch.setenv("GROQ_API_KEY", placeholder_key)
    original_schema = deepcopy(system2.SCHEMA)
    expected_provider_schema = deepcopy(original_schema)
    del expected_provider_schema["properties"]["comments"]["items"]["properties"][
        "evidence"
    ]["uniqueItems"]
    answer = deepcopy(ANSWER)
    if duplicate_evidence:
        answer["comments"][0]["evidence"] *= 2
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        structured = body["response_format"]["json_schema"]
        if "uniqueItems" in json.dumps(structured["schema"]):
            return httpx.Response(
                400,
                json={
                    "error": {
                        "message": "uniqueItems is not supported [unsupported_uniqueItems]"
                    }
                },
            )
        assert structured["strict"] is True
        assert structured["schema"] == expected_provider_schema
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-schema-compatibility",
                "object": "chat.completion",
                "created": 0,
                "model": config.MODEL,
                "system_fingerprint": "fp_projection",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": json.dumps(answer)},
                    }
                ],
                "usage": {
                    "prompt_tokens": 900,
                    "completion_tokens": 250,
                    "total_tokens": 1150,
                },
            },
        )

    with groq.Groq(
        api_key=placeholder_key,
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    ) as sdk:
        monkeypatch.setattr(system2, "client", lambda: sdk)
        if duplicate_evidence:
            with pytest.raises(system2.System2Unavailable) as caught:
                system2.assess(PAYLOAD, WEIGHTS)
            assert caught.value.request_attempted
            assert caught.value.tokens == [900, 250]
            assert not system2._RESULTS
        else:
            result = system2.assess(PAYLOAD, WEIGHTS)
            assert result["score"] == 0.81 and result["request_attempted"]
        assert len(requests) == 1
    assert system2.SCHEMA == original_schema
