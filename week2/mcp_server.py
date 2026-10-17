"""Local stdio MCP server. Stdout is protocol-only; no model access."""

import asyncio
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, TextContent, Tool

from week2 import tools
from week2.contracts import (
    ContractError, NAMES, descriptor, validate_arguments, validate_result,
)

server = Server("cra2-week2")
FUNCTIONS = {NAMES[0]: tools.check_system_health, NAMES[1]: tools.get_dependency_graph}


@server.list_tools()
async def list_tools():
    return [Tool(**descriptor(name)) for name in NAMES]


@server.call_tool(validate_input=False)
async def call_tool(name, arguments):
    try:
        validate_arguments(name, arguments)
        result = FUNCTIONS[name](**arguments)
        validate_result(name, arguments["service_name"], result)
    except ContractError as error:
        code = error.code if error.code == "invalid_input" else "tool_unavailable"
        result = {"status": "error", "error": {"code": code}}
    except Exception:
        result = {"status": "error", "error": {"code": "tool_unavailable"}}
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(result, allow_nan=False))],
        structuredContent=result, isError=False,
    )


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
