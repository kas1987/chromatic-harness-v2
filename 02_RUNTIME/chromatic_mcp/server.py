"""stdio MCP server for Chromatic Harness lite tools."""

from __future__ import annotations

import json
from typing import Any

from chromatic_mcp.handlers import call_tool, list_tool_specs

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    import mcp.types as types
except ImportError as exc:  # pragma: no cover
    Server = None  # type: ignore[misc, assignment]
    stdio_server = None  # type: ignore[misc, assignment]
    types = None  # type: ignore[misc, assignment]
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

SERVER_NAME = "chromatic-harness"


def _build_server() -> Server:
    server = Server(SERVER_NAME)

    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        tools: list[types.Tool] = []
        for spec in list_tool_specs():
            tools.append(
                types.Tool(
                    name=spec["name"],
                    description=spec["description"],
                    inputSchema=spec["inputSchema"],
                )
            )
        return tools

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict[str, Any] | None) -> list[types.TextContent]:
        payload = call_tool(name, arguments)
        text = json.dumps(payload, indent=2, ensure_ascii=False)
        return [types.TextContent(type="text", text=text)]

    return server


async def run_stdio() -> None:
    if Server is None or stdio_server is None:
        raise RuntimeError("mcp package required: pip install mcp>=1.6.0") from _IMPORT_ERROR
    server = _build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    import asyncio

    asyncio.run(run_stdio())


if __name__ == "__main__":
    main()
