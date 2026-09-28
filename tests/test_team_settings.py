"""Offline policy loading and explicit precedence, including false overrides."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from cra2.team_settings import (
    MAX_SETTINGS_CHARACTERS,
    load_settings,
    resolve_settings,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads(
    (ROOT / "data" / "checkout_system.json").read_text(encoding="utf-8")
)["services"]
BASE = {"team": "sample-team", "services": {"auth-service": {"high_risk": True}}}


@pytest.fixture(autouse=True)
def isolated_team_environment(monkeypatch):
    monkeypatch.delenv("CRA2_TEAM_SETTINGS_FILE", raising=False)


def write_settings(directory, value):
    path = directory / "team_settings.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_bundled_sample_is_narrow_and_preserves_catalog():
    original = deepcopy(CATALOG)
    assert load_settings(ROOT / "data", CATALOG) == BASE
    assert CATALOG == original and len(CATALOG) == 8


def test_explicit_file_replaces_bundled_policy(tmp_path, monkeypatch):
    selected = {
        "team": "example-team",
        "services": {"notification-service": {"freeze_window_active": True}},
    }
    path = write_settings(tmp_path, selected)
    monkeypatch.setenv("CRA2_TEAM_SETTINGS_FILE", str(path))
    assert load_settings(tmp_path / "missing-bundled-data", CATALOG) == selected


def test_no_working_directory_settings_are_discovered(tmp_path, monkeypatch):
    write_settings(tmp_path, {"team": "unexpected", "services": {}})
    monkeypatch.chdir(tmp_path)
    assert load_settings(ROOT / "data", CATALOG) == BASE


@pytest.mark.parametrize(
    "document",
    [
        None,
        [],
        True,
        {},
        {"team": "sample-team"},
        {"services": {}},
        {**BASE, "extra": True},
        {**BASE, "team": ""},
        {**BASE, "team": " "},
        {**BASE, "team": "x" * 101},
        {**BASE, "team": 123},
        {**BASE, "team": "a\nb"},
        {**BASE, "services": []},
        {**BASE, "services": {"unknown-service": {}}},
        {**BASE, "services": {"auth-service": []}},
        {**BASE, "services": {"auth-service": {"depends_on": []}}},
    ],
)
def test_settings_schema_is_closed_and_known_services_only(tmp_path, document):
    write_settings(tmp_path, document)
    with pytest.raises(ValueError):
        load_settings(tmp_path, CATALOG)


@pytest.mark.parametrize("field", ["freeze_window_active", "high_risk"])
@pytest.mark.parametrize("value", [0, 1, "true", None, [], {}])
def test_setting_fields_require_actual_booleans(tmp_path, field, value):
    write_settings(tmp_path, {**BASE, "services": {"auth-service": {field: value}}})
    with pytest.raises(ValueError, match="booleans"):
        load_settings(tmp_path, CATALOG)


@pytest.mark.parametrize(
    "case,expected",
    [
        ("invalid", "valid JSON"),
        ("duplicate", "duplicate object keys"),
        ("nonfinite", "nonfinite"),
        ("non-utf8", "UTF-8"),
        ("oversized", "1,048,576 characters"),
        ("deep", "nesting is too deep"),
    ],
)
def test_invalid_file_content_fails_with_bounded_errors(tmp_path, case, expected):
    path = tmp_path / "team_settings.json"
    contents = {
        "invalid": b"not-json",
        "duplicate": b'{"team":"first","team":"second","services":{}}',
        "nonfinite": b'{"team":NaN,"services":{}}',
        "non-utf8": b"\xff\xfe",
        "oversized": b" " * (MAX_SETTINGS_CHARACTERS + 1),
        "deep": b"[" * 50_000 + b"]" * 50_000,
    }
    path.write_bytes(contents[case])
    with pytest.raises(ValueError, match=expected):
        load_settings(tmp_path, CATALOG)


@pytest.mark.parametrize("selected", ["", " ", "missing-private-team-name.json"])
def test_invalid_explicit_path_does_not_echo_path_or_fall_back(
    tmp_path, monkeypatch, selected
):
    write_settings(tmp_path, BASE)
    monkeypatch.setenv("CRA2_TEAM_SETTINGS_FILE", selected)
    with pytest.raises(ValueError, match="CRA2_TEAM_SETTINGS_FILE") as caught:
        load_settings(tmp_path, CATALOG)
    assert "missing-private-team-name" not in str(caught.value)
    assert caught.value.__suppress_context__ or caught.value.__context__ is None


def test_missing_default_file_is_explicit(tmp_path):
    with pytest.raises(ValueError, match="Bundled team settings"):
        load_settings(tmp_path, CATALOG)


def test_unknown_field_or_service_errors_do_not_echo_supplied_values(tmp_path):
    for services in (
        {"private-service-marker": {}},
        {"auth-service": {"private-field-marker": True}},
    ):
        write_settings(tmp_path, {**BASE, "services": services})
        with pytest.raises(ValueError) as caught:
            load_settings(tmp_path, CATALOG)
        assert "private-" not in str(caught.value)


def test_catalog_defaults_do_not_invent_high_risk_evidence():
    result = resolve_settings(
        "notification-service", CATALOG["notification-service"], None, BASE
    )
    assert result["service"]["high_risk"] is False
    assert result["sources"] == {
        "freeze_window_active": "catalog:notification-service.freeze_window_active",
        "high_risk": "default:high_risk",
    }
    assert result["conflicts"] == []
    assert set(result["evidence"]) == set(result["sources"].values())
    assert result["team"] == "sample-team"


@pytest.mark.parametrize("field", ["freeze_window_active", "high_risk"])
@pytest.mark.parametrize("catalog_value", [False, True])
@pytest.mark.parametrize("request_value", [False, True])
@pytest.mark.parametrize("team_value", [False, True])
def test_explicit_team_value_wins_and_disagreement_is_visible(
    field, catalog_value, request_value, team_value
):
    service = {**CATALOG["auth-service"], field: catalog_value}
    settings = {**BASE, "services": {"auth-service": {field: team_value}}}
    result = resolve_settings("auth-service", service, {field: request_value}, settings)
    assert result["service"][field] is team_value
    assert result["sources"][field] == f"team:auth-service.{field}"
    assert f"team:auth-service.{field}" in result["evidence"]
    expected = (
        []
        if request_value == team_value
        else [
            {
                "field": field,
                "requested": request_value,
                "effective": team_value,
                "source": f"team:auth-service.{field}",
            }
        ]
    )
    assert result["conflicts"] == expected


def test_absent_team_fields_leave_request_authoritative_even_when_false():
    result = resolve_settings(
        "auth-service", CATALOG["auth-service"], {"freeze_window_active": False}, BASE
    )
    assert result["service"]["freeze_window_active"] is False
    assert (
        result["sources"]["freeze_window_active"]
        == "change:settings.freeze_window_active"
    )
    assert result["service"]["high_risk"] is True
    assert result["sources"]["high_risk"] == "team:auth-service.high_risk"
    assert result["conflicts"] == []


def test_no_input_objects_or_nested_catalog_data_are_mutated():
    service, request, settings = (
        deepcopy(CATALOG["auth-service"]),
        {"high_risk": False},
        deepcopy(BASE),
    )
    original = deepcopy((service, request, settings))
    result = resolve_settings("auth-service", service, request, settings)
    result["service"]["depends_on"].append("caller-mutation")
    result["service"]["monitors"].append("caller-mutation")
    result["conflicts"][0]["requested"] = True
    assert (service, request, settings) == original


@pytest.mark.parametrize(
    "request_settings", [[], False, {"high_risk": 1}, {"unknown": True}]
)
def test_resolver_rejects_invalid_request_defensively(request_settings):
    with pytest.raises(ValueError, match="Request settings"):
        resolve_settings(
            "auth-service", CATALOG["auth-service"], request_settings, BASE
        )


def test_file_cannot_load_configured_credential_as_team_metadata(tmp_path, monkeypatch):
    sentinel = "local-team-test-credential-sentinel"
    monkeypatch.setenv("GROQ_API_KEY", sentinel)
    write_settings(tmp_path, {**BASE, "team": sentinel})
    with pytest.raises(ValueError, match="credentials") as caught:
        load_settings(tmp_path, CATALOG)
    assert sentinel not in str(caught.value)


@pytest.mark.parametrize("location", ["team", "service", "request"])
def test_resolver_blocks_known_credentials_without_echoing_them(monkeypatch, location):
    sentinel = "local-team-test-credential-sentinel"
    monkeypatch.setenv("GROQ_API_KEY", sentinel)
    service, request_settings, settings = (
        deepcopy(CATALOG["auth-service"]),
        {},
        deepcopy(BASE),
    )
    if location == "team":
        settings["team"] = sentinel
    elif location == "service":
        service["rollback"] = sentinel
    else:
        request_settings[sentinel] = True
    with pytest.raises(ValueError, match="credentials") as caught:
        resolve_settings("auth-service", service, request_settings, settings)
    assert sentinel not in str(caught.value)
