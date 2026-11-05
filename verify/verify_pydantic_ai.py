"""Verify the PydanticAI (MCPToolset + FastMCP StdioTransport) connection to OMX without calling a model."""
from _common import omx_mcp, probe_summary, run

from pydantic_ai_agent import omx_toolset


async def check() -> dict:
    toolset = omx_toolset()
    async with toolset:
        tools = await toolset.list_tools()
        out = await toolset.direct_call_tool(omx_mcp.PROBE_TOOL, dict(omx_mcp.PROBE_ARGS))
    return {"tools": [t.name for t in tools], "probe": {"tool": omx_mcp.PROBE_TOOL, **probe_summary(out)},
            "connection": "pydantic_ai.mcp.MCPToolset(fastmcp StdioTransport(command, args))"}


if __name__ == "__main__":
    run("pydantic-ai", ("pydantic-ai-slim", "fastmcp-slim", "fastmcp"), check)
