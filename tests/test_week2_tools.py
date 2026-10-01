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


@pytest.fixture(params=[tools.check_system_health, tools.get_dependency_graph])
def tool(request):
    return request.param


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
def test_unknown_service(tool, name):
    assert_error(tool(name), "unknown_service")


@pytest.mark.parametrize("name", [None, "", " ", 1, True, [], {}, "a" * 201,
                                  "checkout-service\n", "checkout-service\u202e"])
def test_invalid_name_does_not_read_source(tool, source, name):
    assert_error(tool(name), "invalid_input")


def test_missing_extra_arguments_and_whitespace(tool, source):
    assert_error(tool(), "invalid_input")
    assert_error(tool("checkout-service", "extra"), "invalid_input")
    assert_error(tool("checkout-service", path="../.env"), "invalid_input")
    source.write_text(json.dumps(CATALOG))
    assert tool(" checkout-service ")["service_name"] == "checkout-service"


def test_unavailable_source_does_not_expose_private_path(tool, source):
    assert_error(tool("checkout-service"), "source_unavailable")


@pytest.mark.parametrize("raw", [b"not json", b"\xff", b'{"services":{},"services":{}}',
                                b'{"services":NaN}', b"[" * 20000,
                                b" " * (tools.MAX_SOURCE_CHARACTERS + 1)])
def test_malformed_source_is_not_empty_success(tool, source, raw):
    source.write_bytes(raw)
    assert_error(tool("checkout-service"), "invalid_source")


@pytest.mark.parametrize("document", [None, [], {}, {"services": []}, {"services": {}}])
def test_invalid_catalog_shape(tool, source, document):
    source.write_text(json.dumps(document))
    assert_error(tool("checkout-service"), "invalid_source")


@pytest.mark.parametrize("field,value", [("status", "Unknown"), ("status", []),
    ("freeze_window_active", 1), ("depends_on", "auth-service"),
    ("depends_on", [None]), ("depends_on", ["unlisted-service"])])
def test_invalid_service_record(tool, source, field, value):
    document = deepcopy(CATALOG)
    document["services"]["checkout-service"][field] = value
    source.write_text(json.dumps(document))
    assert_error(tool("checkout-service"), "invalid_source")


@pytest.mark.parametrize("record", [None, []])
def test_invalid_service_object(tool, source, record):
    document = deepcopy(CATALOG)
    document["services"]["checkout-service"] = record
    source.write_text(json.dumps(document))
    assert_error(tool("checkout-service"), "invalid_source")


@pytest.mark.parametrize("name", ["", " private-service", "bad\nname", "a" * 201])
def test_invalid_catalog_identity(tool, source, name):
    source.write_text(json.dumps({"services": {name: CATALOG["services"]["auth-service"]}}))
    assert_error(tool("checkout-service"), "invalid_source")


@pytest.mark.parametrize("credential", ["GROQ_API_KEY", "CRA2_UI_USER", "CRA2_UI_PASSWORD"])
def test_credential_in_input_and_extra_fields_is_rejected_before_read(tool, source, monkeypatch, credential):
    monkeypatch.setenv(credential, FAKE_KEY)
    assert_error(tool(FAKE_KEY), "credential_rejected")
    assert_error(tool("checkout-service", note=FAKE_KEY), "credential_rejected")


@pytest.mark.parametrize("escaped", [False, True])
def test_credential_in_source_is_rejected_without_echo(tool, source, monkeypatch, escaped, capsys):
    monkeypatch.setenv("GROQ_API_KEY", FAKE_KEY)
    document = deepcopy(CATALOG)
    document["note"] = FAKE_KEY
    raw = json.dumps(document)
    if escaped:
        raw = raw.replace(FAKE_KEY, "".join(f"\\u{ord(char):04x}" for char in FAKE_KEY))
    source.write_text(raw)
    assert_error(tool("checkout-service"), "credential_rejected")
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


def test_source_is_reloaded_instead_of_returning_stale_health(source):
    document = deepcopy(CATALOG)
    source.write_text(json.dumps(document))
    assert tools.check_system_health("checkout-service")["health"] == "Healthy"
    document["services"]["checkout-service"]["status"] = "Degraded"
    source.write_text(json.dumps(document))
    assert tools.check_system_health("checkout-service")["health"] == "Degraded"


# Week 2 task 14: both graph directions come from edges, including transitive callers.
def test_payment_graph_matches_recorded_directions():
    result = tools.get_dependency_graph("payment-gateway")
    assert result == {
        "status": "ok", "service_name": "payment-gateway",
        "dependents": {
            "direct": ["checkout-service"],
            "transitive": ["checkout-service", "mobile-frontend", "order-service", "web-frontend"],
        },
        "dependencies": {"direct": ["notification-service"], "transitive": ["notification-service"]},
        "source": {"path": "data/checkout_system.json", "kind": "synthetic_snapshot",
                   "observed_at": None, "freshness": "unknown"},
        "evidence": ["graph:payment-gateway.dependents", "graph:payment-gateway.dependencies"],
    }


def test_checkout_graph_separates_direct_and_transitive():
    result = tools.get_dependency_graph("checkout-service")
    assert result["dependents"] == {
        "direct": ["order-service"],
        "transitive": ["mobile-frontend", "order-service", "web-frontend"],
    }
    assert result["dependencies"] == {
        "direct": ["auth-service", "inventory-service", "payment-gateway"],
        "transitive": ["auth-service", "inventory-service", "notification-service", "payment-gateway"],
    }


def test_cycles_self_edges_and_duplicate_edges(source):
    document = deepcopy(CATALOG)
    document["services"]["checkout-service"]["depends_on"] += ["checkout-service", "auth-service"]
    document["services"]["auth-service"]["depends_on"] = ["checkout-service"]
    source.write_text(json.dumps(document))
    result = tools.get_dependency_graph("checkout-service")
    assert result["dependents"] == {
        "direct": ["auth-service", "order-service"],
        "transitive": ["auth-service", "mobile-frontend", "order-service", "web-frontend"],
    }
    assert result["dependencies"] == {
        "direct": ["auth-service", "inventory-service", "payment-gateway"],
        "transitive": ["auth-service", "inventory-service", "notification-service", "payment-gateway"],
    }


def test_isolated_service_returns_valid_empty_lists(source):
    document = deepcopy(CATALOG)
    document["services"]["isolated-service"] = deepcopy(document["services"]["auth-service"])
    source.write_text(json.dumps(document))
    result = tools.get_dependency_graph("isolated-service")
    assert result["status"] == "ok"
    assert result["dependents"] == result["dependencies"] == {"direct": [], "transitive": []}


def test_long_graph_uses_iterative_traversal(source):
    size = 1200
    services = {
        f"service-{i}": {"status": "Healthy", "freeze_window_active": False,
                          "depends_on": [f"service-{i+1}"] if i+1 < size else []}
        for i in range(size)
    }
    source.write_text(json.dumps({"services": services}))
    result = tools.get_dependency_graph("service-0")
    assert result["status"] == "ok"
    assert result["dependencies"]["direct"] == ["service-1"]
    assert result["dependencies"]["transitive"] == sorted(set(services) - {"service-0"})
    assert result["dependents"] == {"direct": [], "transitive": []}


def test_source_is_reloaded_instead_of_returning_stale_edges(source):
    document = deepcopy(CATALOG)
    source.write_text(json.dumps(document))
    assert tools.get_dependency_graph("payment-gateway")["dependents"]["direct"] == ["checkout-service"]
    document["services"]["checkout-service"]["depends_on"].remove("payment-gateway")
    source.write_text(json.dumps(document))
    assert tools.get_dependency_graph("payment-gateway")["dependents"] == {"direct": [], "transitive": []}


def test_credential_introduced_by_output_is_rejected(tool, monkeypatch):
    prefix = "catalog" if tool is tools.check_system_health else "graph"
    suffix = "status" if tool is tools.check_system_health else "dependents"
    monkeypatch.setenv("GROQ_API_KEY", f"{prefix}:checkout-service.{suffix}")
    assert_error(tool("checkout-service"), "credential_rejected")


def test_tools_leave_source_unchanged_and_do_not_call_a_provider(tool, monkeypatch):
    from cra2 import system2
    before = tools.CATALOG_PATH.read_bytes()

    def forbidden():
        raise AssertionError("Local tools must not call a model provider")

    monkeypatch.setattr(system2, "client", forbidden)
    assert tool("checkout-service")["status"] == "ok"
    assert tools.CATALOG_PATH.read_bytes() == before
