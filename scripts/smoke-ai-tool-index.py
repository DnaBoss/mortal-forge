#!/usr/bin/env python3
"""Exercise the installed stdio MCP using the existing Python MCP client."""

import asyncio
import json
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import McpError


async def check(home=None):
    binary = str(Path.home() / ".local/bin/ai-tool-index-mcp")
    parameters = StdioServerParameters(
        command=binary, env={"HOME": home} if home else None
    )
    async with (
        stdio_client(parameters) as (read, write),
        ClientSession(read, write) as client,
    ):
        await client.initialize()
        tools = await client.list_tools()
        assert [tool.name for tool in tools.tools] == ["ai_tool_index"]
        try:
            result = await client.call_tool(
                "ai_tool_index", {"query": "codegraph", "limit": 3}
            )
        except McpError as error:
            assert home and error.error.code == -32603
            return "missing_index_rejected"
        assert not home, "Missing index unexpectedly accepted"
        assert not result.isError
        value = result.structuredContent
        assert value["total"] >= 1
        assert any(item["name"] == "codegraph" for item in value["items"])
        try:
            await client.call_tool("ai_tool_index", {"limit": 101})
        except McpError as error:
            assert error.error.code == -32602
        else:
            raise AssertionError("Invalid limit unexpectedly accepted")
        return {
            "query": "codegraph",
            "total": value["total"],
            "invalid_limit_rejected": True,
        }


async def main():
    result = await asyncio.wait_for(check(), timeout=15)
    with tempfile.TemporaryDirectory() as home:
        negative = await asyncio.wait_for(check(home), timeout=15)
    print(json.dumps({"ok": True, "positive": result, "negative": negative}))


if __name__ == "__main__":
    asyncio.run(main())
