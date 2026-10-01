"""Week 2 tasks 13–14: source, failure, and credential boundary proofs."""

import json
from copy import deepcopy

import pytest

from week2 import tools

CATALOG = json.loads(tools.CATALOG_PATH.read_text(encoding="utf-8"))
FAKE_KEY = "CRA2_WEEK2_FAKE_CREDENTIAL_CANARY_123456789"


@pytest.fixture(autouse=True)
def isolated_credentials(monkeypatch):
    for name in ("GROQ_API_KEY", "CRA2_UI_USER", "CRA2_UI_PASSWORD"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def source(tmp_path, monkeypatch):
    path = tmp_path / "private-snapshot.json"
    monkeypatch.setattr(tools, "CATALOG_PATH", path)
    return path


def assert_error(result, code):
    assert result == {"status": "error", "error": {"code": code}}


# Week 2 task 13: known snapshots retain recorded facts and unknown operational state.
@pytest.mark.parametrize(
    "name,health,active",
    [("checkout-service", "Healthy", False), ("payment-gateway", "Degraded", False),
     ("auth-service", "Healthy", True)],
)
def test_health_known_service(name, health, active):
    result = tools.check_system_health(name)
    assert result == {
        "status": "ok", "service_name": name, "health": health,
        "active_incidents": None, "active_incidents_status": "unknown",
        "freeze_window": {"reported_active": active,
                          "status": "unconfirmed" if active else "not_reported"},
        "source": {"path": "data/checkout_system.json", "kind": "synthetic_snapshot",
                   "observed_at": None, "freshness": "unknown"},
        "evidence": [f"catalog:{name}.status", f"catalog:{name}.freeze_window_active"],
    }


@pytest.mark.parametrize("name", ["unknown-service", "Checkout-service", "../.env"])
def test_health_unknown_service(name):
    assert_error(tools.check_system_health(name), "unknown_service")


@pytest.mark.parametrize("name", [None, "", " ", 1, True, [], {}, "a" * 201,
                                  "checkout-service\n", "checkout-service\u202e"])
def test_invalid_name_does_not_read_source(source, name):
    assert_error(tools.check_system_health(name), "invalid_input")


def test_missing_extra_arguments_and_whitespace(source):
    assert_error(tools.check_system_health(), "invalid_input")
    assert_error(tools.check_system_health("checkout-service", "extra"), "invalid_input")
    assert_error(tools.check_system_health("checkout-service", path="../.env"), "invalid_input")
    source.write_text(json.dumps(CATALOG))
    assert tools.check_system_health(" checkout-service ")["service_name"] == "checkout-service"


def test_unavailable_source_does_not_expose_private_path(source):
    assert_error(tools.check_system_health("checkout-service"), "source_unavailable")


@pytest.mark.parametrize("raw", [b"not json", b"\xff", b'{"services":{},"services":{}}',
                                b'{"services":NaN}', b"[" * 20000,
                                b" " * (tools.MAX_SOURCE_CHARACTERS + 1)])
def test_malformed_source_is_not_empty_success(source, raw):
    source.write_bytes(raw)
    assert_error(tools.check_system_health("checkout-service"), "invalid_source")


@pytest.mark.parametrize("document", [None, [], {}, {"services": []}, {"services": {}}])
def test_invalid_catalog_shape(source, document):
    source.write_text(json.dumps(document))
    assert_error(tools.check_system_health("checkout-service"), "invalid_source")


@pytest.mark.parametrize("field,value", [("status", "Unknown"), ("status", []),
    ("freeze_window_active", 1), ("depends_on", "auth-service"),
    ("depends_on", [None]), ("depends_on", ["unlisted-service"])])
def test_invalid_service_record(source, field, value):
    document = deepcopy(CATALOG)
    document["services"]["checkout-service"][field] = value
    source.write_text(json.dumps(document))
    assert_error(tools.check_system_health("checkout-service"), "invalid_source")


@pytest.mark.parametrize("record", [None, []])
def test_invalid_service_object(source, record):
    document = deepcopy(CATALOG)
    document["services"]["checkout-service"] = record
    source.write_text(json.dumps(document))
    assert_error(tools.check_system_health("checkout-service"), "invalid_source")


@pytest.mark.parametrize("name", ["", " private-service", "bad\nname", "a" * 201])
def test_invalid_catalog_identity(source, name):
    source.write_text(json.dumps({"services": {name: CATALOG["services"]["auth-service"]}}))
    assert_error(tools.check_system_health("checkout-service"), "invalid_source")


@pytest.mark.parametrize("credential", ["GROQ_API_KEY", "CRA2_UI_USER", "CRA2_UI_PASSWORD"])
def test_credential_in_input_and_extra_fields_is_rejected_before_read(source, monkeypatch, credential):
    monkeypatch.setenv(credential, FAKE_KEY)
    assert_error(tools.check_system_health(FAKE_KEY), "credential_rejected")
    assert_error(tools.check_system_health("checkout-service", note=FAKE_KEY), "credential_rejected")


@pytest.mark.parametrize("escaped", [False, True])
def test_credential_in_source_is_rejected_without_echo(source, monkeypatch, escaped, capsys):
    monkeypatch.setenv("GROQ_API_KEY", FAKE_KEY)
    document = deepcopy(CATALOG)
    document["note"] = FAKE_KEY
    raw = json.dumps(document)
    if escaped:
        raw = raw.replace(FAKE_KEY, "".join(f"\\u{ord(char):04x}" for char in FAKE_KEY))
    source.write_text(raw)
    assert_error(tools.check_system_health("checkout-service"), "credential_rejected")
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


def test_source_is_reloaded_instead_of_returning_stale_health(source):
    document = deepcopy(CATALOG)
    source.write_text(json.dumps(document))
    assert tools.check_system_health("checkout-service")["health"] == "Healthy"
    document["services"]["checkout-service"]["status"] = "Degraded"
    source.write_text(json.dumps(document))
    assert tools.check_system_health("checkout-service")["health"] == "Degraded"
