"""Verify the OpenAI Agents SDK connection to OMX without calling a model."""
from _common import omx_mcp, probe_summary, run

from openai_agents_agent import omx_server


async def check() -> dict:
    async with omx_server() as server:
        tools = await server.list_tools()
        res = await server.call_tool(omx_mcp.PROBE_TOOL, dict(omx_mcp.PROBE_ARGS))
    body = res.structuredContent if getattr(res, "structuredContent", None) else (
        res.content[0].text if res.content else None)
    return {"tools": [t.name for t in tools], "probe": {"tool": omx_mcp.PROBE_TOOL, **probe_summary(body)},
            "connection": "agents.mcp.MCPServerStdio(params={command, args})"}


if __name__ == "__main__":
    run("openai-agents", ("openai-agents",), check)
