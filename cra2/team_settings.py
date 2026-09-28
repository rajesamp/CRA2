"""Explicit team policy and request settings with visible precedence and provenance."""

import json
import os
import unicodedata
from copy import deepcopy
from pathlib import Path

from cra2.secrets import reject_credentials

SETTING_FIELDS = ("freeze_window_active", "high_risk")
MAX_SETTINGS_CHARACTERS = 1024 * 1024


class SettingsError(ValueError):
    """Invalid settings, reported without echoing file contents or supplied values."""


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise SettingsError("Team settings contain duplicate object keys")
        result[key] = value
    return result


def _reject_constant(_value: str):
    raise SettingsError("Team settings must not contain nonfinite JSON numbers")


def _validate_fields(value: object, label: str) -> None:
    if not isinstance(value, dict):
        raise SettingsError(f"{label} must be an object")
    if value.keys() - set(SETTING_FIELDS):
        raise SettingsError(f"{label} contain unsupported fields")
    if any(type(item) is not bool for item in value.values()):
        raise SettingsError(f"{label} values must be booleans")


def _validate_settings(settings: object, catalog: dict | None = None) -> None:
    if not isinstance(settings, dict) or set(settings) != {"team", "services"}:
        raise SettingsError("Team settings must contain exactly team and services")
    team = settings["team"]
    if (
        not isinstance(team, str)
        or not team.strip()
        or len(team) > 100
        or any(unicodedata.category(char).startswith("C") for char in team)
    ):
        raise SettingsError(
            "Team name must be a nonempty string of at most 100 characters without controls"
        )
    overrides = settings["services"]
    if not isinstance(overrides, dict):
        raise SettingsError("Team services must be an object")
    if catalog is not None and overrides.keys() - catalog.keys():
        raise SettingsError("Team settings contain an unknown catalog service")
    for name, fields in overrides.items():
        if (
            not isinstance(name, str)
            or not name.strip()
            or len(name) > 200
            or any(unicodedata.category(char).startswith("C") for char in name)
        ):
            raise SettingsError(
                "Team service names must be bounded nonempty strings without controls"
            )
        _validate_fields(fields, "Team service settings")


def load_settings(data_dir: Path, catalog: dict) -> dict:
    """Load bundled settings or the explicitly selected CRA2_TEAM_SETTINGS_FILE.

    An override file replaces the bundled policy; no settings are implicitly
    discovered in the working directory. Input is bounded in decoded characters.
    """
    selected = os.environ.get("CRA2_TEAM_SETTINGS_FILE")
    if selected is not None and not selected.strip():
        raise SettingsError(
            "CRA2_TEAM_SETTINGS_FILE must name a readable UTF-8 JSON file"
        )
    try:
        path = (
            Path(selected).expanduser()
            if selected is not None
            else data_dir / "team_settings.json"
        )
        with path.open(encoding="utf-8") as stream:
            text = stream.read(MAX_SETTINGS_CHARACTERS + 1)
    except (OSError, UnicodeError, ValueError):
        label = (
            "CRA2_TEAM_SETTINGS_FILE"
            if selected is not None
            else "Bundled team settings"
        )
        raise SettingsError(f"{label} must name a readable UTF-8 JSON file") from None
    if len(text) > MAX_SETTINGS_CHARACTERS:
        raise SettingsError("Team settings exceed 1,048,576 characters")
    try:
        settings = json.loads(
            text, object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
    except SettingsError:
        raise
    except RecursionError:
        raise SettingsError("Team settings JSON nesting is too deep") from None
    except ValueError:
        raise SettingsError("Team settings must contain valid JSON") from None
    reject_credentials(settings)
    _validate_settings(settings, catalog)
    return settings


def resolve_settings(
    name: str, service: dict, request_settings: dict | None, settings: dict
) -> dict:
    """Resolve catalog defaults, request fields, then explicitly present team fields.

    Team policy wins even when its value is false. Conflicts describe request
    values changed by team policy, and sources identify each effective authority.
    """
    reject_credentials((name, service, request_settings, settings))
    _validate_settings(settings)
    request = {} if request_settings is None else request_settings
    _validate_fields(request, "Request settings")
    if not isinstance(service, dict):
        raise SettingsError("Catalog service must be an object")
    team_fields = settings["services"].get(name, {})
    effective, sources, conflicts = deepcopy(service), {}, []
    for field in SETTING_FIELDS:
        initial = service.get(field, False)
        if type(initial) is not bool:
            raise SettingsError("Catalog setting values must be booleans")
        effective[field] = initial
        sources[field] = (
            f"catalog:{name}.{field}" if field in service else f"default:{field}"
        )
        if field in request:
            effective[field] = request[field]
            sources[field] = f"change:settings.{field}"
        if field in team_fields:
            effective[field] = team_fields[field]
            sources[field] = f"team:{name}.{field}"
            if field in request and request[field] != team_fields[field]:
                conflicts.append(
                    {
                        "field": field,
                        "requested": request[field],
                        "effective": team_fields[field],
                        "source": sources[field],
                    }
                )
    return {
        "service": effective,
        "sources": sources,
        "conflicts": conflicts,
        "evidence": sorted(set(sources.values())),
        "team": settings["team"],
    }
