"""Bounded MCP lifecycle, reviewed metadata gate, and sanitized execution events."""

import math
import os
import subprocess
import sys
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from week2.contracts import (
    ContractError, NAMES, decode_json, validate_arguments, validate_inventory,
    validate_result,
)

ROOT = Path(__file__).resolve().parents[1]


def server_parameters():
    # MCP's stdio helper also inherits its documented safe OS environment subset.
    # Deliberately omit provider keys, selected dotenv, UI auth and arbitrary env.
    return StdioServerParameters(
        command=sys.executable, args=["-m", "week2.mcp_server"], cwd=str(ROOT),
        env={"PYTHONPATH": str(ROOT), "PYTHONNOUSERSITE": "1", "PATH": os.defpath},
    )


async def _inventory(session):
    listed = await session.list_tools()
    if listed.nextCursor is not None:
        raise ContractError("metadata_rejected")
    # Dump ALL received fields: extra SDK fields cannot be silently discarded.
    return validate_inventory([
        tool.model_dump(mode="json", by_alias=True, exclude_none=True)
        for tool in listed.tools
    ])


def _decode(reply, name, service):
    if (reply.isError or len(reply.content) != 1
            or reply.content[0].type != "text"):
        raise ContractError("invalid_result")
    result = decode_json(reply.content[0].text)
    if reply.structuredContent != result:
        raise ContractError("invalid_result")
    return validate_result(name, service, result)


def _failure_code(error):
    if isinstance(error, ContractError):
        return error.code
    if isinstance(error, TimeoutError):
        return "timeout"
    for nested in getattr(error, "exceptions", ()):
        code = _failure_code(nested)
        if code != "transport_unavailable":
            return code
    return "transport_unavailable"


async def call_tools(calls, *, timeout=12.0):
    """At most two unique calls, one deadline including discovery and shutdown.

    A transport/gate failure discards partial outputs. Error events contain only
    locally defined codes; rejected metadata and raw exceptions never propagate.
    """
    events, outputs = [], {}
    try:
        if (not isinstance(calls, list) or not 1 <= len(calls) <= 2
                or type(timeout) not in (float, int) or not math.isfinite(timeout)
                or not 0 < timeout <= 30):
            raise ContractError("invalid_input")
        seen = set()
        for name, arguments in calls:
            validate_arguments(name, arguments)
            if name in seen:
                raise ContractError("invalid_input")
            seen.add(name)
        with anyio.fail_after(timeout):
            async with stdio_client(server_parameters(), errlog=subprocess.DEVNULL) as streams:
                async with ClientSession(*streams) as session:
                    await session.initialize()
                    await _inventory(session)
                    events.append({"event": "metadata_admitted", "tools": list(NAMES)})
                    for name, arguments in calls:
                        await _inventory(session)
                        reply = await session.call_tool(name, arguments)
                        result = _decode(reply, name, arguments["service_name"])
                        outputs[name] = result
                        events.append({"event": "tool_result", "transport": "mcp-stdio",
                                       "tool": name, "input": arguments, "output": result})
        return {"status": "ok", "outputs": outputs, "events": events}
    except ContractError as error:
        code = error.code
    except TimeoutError:
        code = "timeout"
    except Exception as error:
        # AnyIO task groups can wrap protocol errors; do not expose nested text.
        code = _failure_code(error)
    return {"status": "error", "outputs": {},
            "events": [{"event": "mcp_failed", "code": code}]}
