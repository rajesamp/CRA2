"""Credential boundary proofs using only an explicitly fake sentinel key."""

import json
import logging
import traceback
from copy import deepcopy
from types import SimpleNamespace

import groq
import httpx
import pytest

from cra2 import advisor, config, system2
from cra2.secrets import reject_credentials

FAKE_KEY = "gsk_CRA2_SENTINEL_NOT_A_REAL_CREDENTIAL_123456789"
WEIGHTS = {
    "rating_value": {"none": 0, "low": 0.33, "medium": 0.67, "high": 1},
    "worst_weight": 0.6,
}
PAYLOAD = {
    "change": {"summary": "Batch email sends"},
    "evidence_keys": ["change:summary"],
}
ANSWER = {
    "ratings": dict.fromkeys(
        ("deploy_order", "rollback", "config_drift", "dependencies", "monitoring"),
        "low",
    ),
    "comments": [
        {
            "tag": tag,
            "severity": "low",
            "text": "Check queue consumer behavior.",
            "evidence": ["change:summary"],
        }
        for tag in ("dependencies", "monitoring", "rollback")
    ],
}


@pytest.fixture(autouse=True)
def fake_credentials(monkeypatch):
    # Never load or inspect a developer's real dotenv credential.
    monkeypatch.setenv("GROQ_API_KEY", FAKE_KEY)
    system2.call.cache_clear()
    yield
    system2.call.cache_clear()


def install_fake(
    monkeypatch, *, answer=None, model=None, fingerprint="fp_placeholder", refusal=None
):
    requests = []

    def create(**kwargs):
        requests.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(
                        content=json.dumps(ANSWER if answer is None else answer),
                        refusal=refusal,
                    ),
                )
            ],
            model=config.MODEL if model is None else model,
            system_fingerprint=fingerprint,
            usage=SimpleNamespace(
                prompt_tokens=20, completion_tokens=10, total_time=0.01
            ),
        )

    sdk = SimpleNamespace(
        api_key=FAKE_KEY,
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
    )
    monkeypatch.setattr(system2, "client", lambda: sdk)
    return requests


def assert_safe_failure(caught, *, attempted):
    error = caught.value
    assert error.request_attempted is attempted
    assert error.__cause__ is None and error.__context__ is None
    assert FAKE_KEY not in str(error)
    assert FAKE_KEY not in "".join(traceback.format_exception(error))
    assert not system2._RESULTS


@pytest.mark.parametrize(
    "value",
    [
        FAKE_KEY,
        {FAKE_KEY: "value"},
        {"nested": ["prefix " + FAKE_KEY]},
        [({"value": FAKE_KEY},)],
    ],
)
def test_recursive_guard_rejects_credential_in_strings_or_keys(value):
    with pytest.raises(ValueError) as caught:
        reject_credentials(value)
    assert FAKE_KEY not in str(caught.value)


def test_guard_allows_ordinary_data_and_does_not_invent_credentials(monkeypatch):
    reject_credentials({"example": "test", "count": 1})
    monkeypatch.delenv("GROQ_API_KEY")
    reject_credentials({"sample": FAKE_KEY})


def test_guard_handles_cycles_without_logging_or_formatting_values():
    value = []
    value.append(value)
    reject_credentials(value)
    value.append(FAKE_KEY)
    with pytest.raises(ValueError):
        reject_credentials(value)


def test_payload_credential_is_rejected_before_network_or_cache(monkeypatch):
    requests = install_fake(monkeypatch)
    with pytest.raises(system2.System2Unavailable) as caught:
        system2.assess({**PAYLOAD, "secret": FAKE_KEY}, WEIGHTS)
    assert requests == []
    assert_safe_failure(caught, attempted=False)


def test_prompt_credential_is_rejected_before_network_or_cache(monkeypatch):
    requests = install_fake(monkeypatch)
    monkeypatch.setattr(system2, "PROMPT", system2.PROMPT + FAKE_KEY)
    with pytest.raises(system2.System2Unavailable) as caught:
        system2.assess(PAYLOAD, WEIGHTS)
    assert requests == []
    assert_safe_failure(caught, attempted=False)


def test_active_sdk_key_is_protected_after_environment_rotation(monkeypatch):
    requests = install_fake(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_ANOTHER_FAKE_SENTINEL_0987654321")
    with pytest.raises(system2.System2Unavailable) as caught:
        system2.assess({**PAYLOAD, "secret": FAKE_KEY}, WEIGHTS)
    assert requests == []
    assert_safe_failure(caught, attempted=False)


@pytest.mark.parametrize(
    "field", ["text", "evidence", "model", "fingerprint", "refusal"]
)
def test_credential_echo_in_provider_content_or_metadata_is_not_cached_or_returned(
    monkeypatch, field
):
    answer = deepcopy(ANSWER)
    options = {}
    if field == "text":
        answer["comments"][0]["text"] = "Check " + FAKE_KEY
    elif field == "evidence":
        answer["comments"][0]["evidence"] = [FAKE_KEY]
    else:
        options[field] = FAKE_KEY
    requests = install_fake(monkeypatch, answer=answer, **options)
    with pytest.raises(system2.System2Unavailable) as caught:
        system2.assess(PAYLOAD, WEIGHTS)
    assert len(requests) == 1
    assert caught.value.tokens == [20, 10]
    assert_safe_failure(caught, attempted=True)


def test_credential_added_to_environment_after_cache_population_is_blocked(monkeypatch):
    old_key = "gsk_OTHER_PLACEHOLDER_KEY"
    monkeypatch.setenv("GROQ_API_KEY", old_key)
    requests = install_fake(monkeypatch, model=FAKE_KEY)
    # Make the first SDK use a different credential; the provider's model string
    # becomes a credential only after rotation. Existing cache values need checks.
    sdk = system2.client()
    sdk.api_key = old_key
    system2.assess(PAYLOAD, WEIGHTS)
    monkeypatch.setenv("GROQ_API_KEY", FAKE_KEY)
    with pytest.raises(system2.System2Unavailable) as caught:
        system2.assess(PAYLOAD, WEIGHTS)
    assert len(requests) == 1
    assert_safe_failure(caught, attempted=False)


def test_client_initialization_error_has_no_sensitive_chain(monkeypatch):
    def broken():
        raise groq.GroqError("Invalid authentication " + FAKE_KEY)

    monkeypatch.setattr(system2, "client", broken)
    with pytest.raises(system2.System2Unavailable) as caught:
        system2.assess(PAYLOAD, WEIGHTS)
    assert_safe_failure(caught, attempted=False)


@pytest.mark.parametrize("failure_kind", ["http_error", "connection_error"])
def test_real_sdk_debug_logs_and_error_chains_cannot_echo_credential(
    monkeypatch, caplog, failure_kind
):
    real_factory = groq.Groq
    requests = []
    names = ("groq", "groq._base_client", "httpx", "httpcore.connection")
    saved = {}
    for name in names:
        logger = logging.getLogger(name)
        saved[name] = (
            logger.disabled,
            logger.level,
            logger.propagate,
            list(logger.handlers),
        )
        logger.disabled = False
        logger.setLevel(logging.DEBUG)
        logger.propagate = True
    caplog.set_level(logging.DEBUG)
    logging.getLogger("cra2_test_canary").warning("Visible logging canary")

    def handler(request):
        assert request.headers["Authorization"] == "Bearer " + FAKE_KEY
        assert FAKE_KEY.encode() not in request.content
        requests.append(request.url.host)
        for name in names:
            logging.getLogger(name).debug("Authorization Bearer %s", FAKE_KEY)
        if failure_kind == "connection_error":
            raise httpx.ReadTimeout("Provider echoed " + FAKE_KEY, request=request)
        return httpx.Response(
            401, json={"error": {"message": "Provider echoed " + FAKE_KEY}}
        )

    def factory(**kwargs):
        return real_factory(
            api_key=FAKE_KEY,
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            **kwargs,
        )

    system2.client.cache_clear()
    monkeypatch.setattr(groq, "Groq", factory)
    monkeypatch.setenv("GROQ_BASE_URL", "https://untrusted.example.invalid")
    try:
        with pytest.raises(system2.System2Unavailable) as caught:
            system2.assess(PAYLOAD, WEIGHTS)
        assert_safe_failure(caught, attempted=True)
        assert requests == ["api.groq.com"]
        assert "Visible logging canary" in caplog.text
        assert FAKE_KEY not in caplog.text
    finally:
        system2.client().close()
        system2.client.cache_clear()
        for name, state in saved.items():
            logger = logging.getLogger(name)
            logger.disabled, logger.level, logger.propagate, logger.handlers = state


@pytest.mark.parametrize("field", ["summary", "rollback_plan", "id"])
def test_fast_mode_rejects_credential_before_reflecting_user_data(field):
    change = {
        "service": "notification-service",
        "change_type": "Code deploy",
        "summary": "Batch email sends.",
        field: "Text containing " + FAKE_KEY,
    }
    with pytest.raises(ValueError) as caught:
        advisor.assess(change, "fast")
    assert FAKE_KEY not in str(caught.value)


def test_fast_mode_rejects_credential_in_incident_context(monkeypatch):
    incident = {**advisor.INCIDENTS[0], "root_cause": FAKE_KEY}
    monkeypatch.setattr(advisor, "INCIDENTS", [incident])
    with pytest.raises(ValueError) as caught:
        advisor.assess(
            {
                "service": incident["service"],
                "change_type": "Config change",
                "summary": "Reduce payment timeout from 5000 to 500 milliseconds.",
            },
            "fast",
        )
    assert FAKE_KEY not in str(caught.value)


def test_renderer_rejects_credential_in_external_result():
    with pytest.raises(ValueError) as caught:
        advisor.render({"note": FAKE_KEY})
    assert FAKE_KEY not in str(caught.value)


def test_clarification_rejects_credential_in_catalog_identity(monkeypatch):
    monkeypatch.setattr(advisor, "CATALOG", {FAKE_KEY: {}})
    with pytest.raises(ValueError) as caught:
        advisor.assess({}, "fast")
    assert FAKE_KEY not in str(caught.value)
