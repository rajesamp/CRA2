"""Week 2 tasks 13–14: validated read-only tools over the canonical snapshot."""

import json
import os
import unicodedata

from cra2.config import DATA_DIR
from cra2.secrets import reject_credentials

CATALOG_PATH = DATA_DIR / "checkout_system.json"
MAX_SOURCE_CHARACTERS = 1024 * 1024


# Week 2 tasks 13–14 share bounded source validation and protected error handling.
class _ToolError(ValueError):
    pass


def _guard(value):
    try:
        reject_credentials(
            value, additional=(os.getenv("CRA2_UI_USER"), os.getenv("CRA2_UI_PASSWORD"))
        )
    except ValueError:
        raise _ToolError("credential_rejected") from None


def _valid_name(value):
    return (
        isinstance(value, str)
        and 0 < len(value) <= 200
        and bool(value.strip())
        and not any(unicodedata.category(char).startswith("C") for char in value)
    )


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _ToolError("invalid_source")
        result[key] = value
    return result


def _reject_constant(_value):
    raise _ToolError("invalid_source")


def _context(service_name, extra, fields):
    _guard((service_name, extra, fields))
    if extra or fields or not _valid_name(service_name):
        raise _ToolError("invalid_input")
    try:
        with CATALOG_PATH.open(encoding="utf-8") as stream:
            raw = stream.read(MAX_SOURCE_CHARACTERS + 1)
    except UnicodeError:
        raise _ToolError("invalid_source") from None
    except OSError:
        raise _ToolError("source_unavailable") from None
    _guard(raw)
    if len(raw) > MAX_SOURCE_CHARACTERS:
        raise _ToolError("invalid_source")
    try:
        data = json.loads(
            raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
    except (ValueError, RecursionError):
        raise _ToolError("invalid_source") from None
    _guard(data)
    services = data.get("services") if isinstance(data, dict) else None
    if not isinstance(services, dict) or not services:
        raise _ToolError("invalid_source")
    for name, record in services.items():
        if not _valid_name(name) or name != name.strip() or not isinstance(record, dict):
            raise _ToolError("invalid_source")
        edges = record.get("depends_on")
        if (
            record.get("status") not in ("Healthy", "Degraded")
            or type(record.get("freeze_window_active")) is not bool
            or not isinstance(edges, list)
            or any(not isinstance(edge, str) or edge not in services for edge in edges)
        ):
            raise _ToolError("invalid_source")
    name = service_name.strip()
    if name not in services:
        raise _ToolError("unknown_service")
    return name, services


def _reply(name, fields, evidence):
    result = {
        "status": "ok",
        "service_name": name,
        **fields,
        "source": {
            "path": "data/checkout_system.json",
            "kind": "synthetic_snapshot",
            "observed_at": None,
            "freshness": "unknown",
        },
        "evidence": evidence,
    }
    _guard(result)
    return result


# Week 2 task 13: recorded health and freeze reports, never current-state claims.
def check_system_health(service_name=None, *extra, **fields):
    """Return snapshot facts or a safe error; malformed arguments never trigger lookup."""
    try:
        name, services = _context(service_name, extra, fields)
        service = services[name]
        active = service["freeze_window_active"]
        return _reply(
            name,
            {
                "health": service["status"],
                "active_incidents": None,
                "active_incidents_status": "unknown",
                "freeze_window": {
                    "reported_active": active,
                    "status": "unconfirmed" if active else "not_reported",
                },
            },
            [f"catalog:{name}.status", f"catalog:{name}.freeze_window_active"],
        )
    except _ToolError as error:
        return {"status": "error", "error": {"code": str(error)}}
