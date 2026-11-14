"""Integration tests for MCP stub server."""

import asyncio
import sys
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def run_mcp_session(coro):
    """Open stdio session to lazarus.mcp and run a coroutine."""
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "lazarus.mcp"],
        cwd=Path(__file__).parent.parent
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await coro(session)


def test_list_tools():
    """List tools and verify get_verdict with required output schema fields."""
    async def check(session):
        result = await session.list_tools()
        tools = {tool.name: tool for tool in result.tools}
        assert "get_verdict" in tools
        schema = tools["get_verdict"].input_schema
        assert schema["required"] == ["project_id"]
        assert set(tools["get_verdict"].output_schema["required"]) == {"verdict", "divergences", "test_cases", "message"}
        
    asyncio.run(run_mcp_session(check))


def test_get_verdict_success():
    """Call get_verdict with project_id returns exact stub response."""
    async def check(session):
        result = await session.call_tool("get_verdict", arguments={"project_id": "test"})
        assert result.is_error is False
        expected = {
            "verdict": "VIVANT",
            "divergences": 0,
            "test_cases": 1,
            "message": "0 divergence found on 1 case (stub)"
        }
        assert result.structured_content == expected
        
    asyncio.run(run_mcp_session(check))


def test_get_verdict_missing_project_id():
    """Call get_verdict without project_id returns MCP error with Field required."""
    async def check(session):
        result = await session.call_tool("get_verdict", arguments={})
        assert result.is_error is True
        assert "Field required" in result.content[0].text
        
    asyncio.run(run_mcp_session(check))
