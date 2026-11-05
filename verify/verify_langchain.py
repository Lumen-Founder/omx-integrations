"""Verify the LangChain (langchain.mcp.MCPAdapter) connection to OMX without calling a model."""
from _common import match_tools, omx_mcp, probe_summary, run

from langchain_agent import omx_adapter


async def check() -> dict:
    async with omx_adapter() as adapter:
        tools = await adapter.list_tools()
        names = [t.name for t in tools]
        probe_name = match_tools(names)["mapped"].get(omx_mcp.PROBE_TOOL)
        out = await next(t for t in tools if t.name == probe_name).ainvoke(dict(omx_mcp.PROBE_ARGS)) if probe_name else None
    body = out
    if isinstance(out, list) and out and isinstance(out[0], dict):   # content blocks
        body = out[0].get("text", out)
    elif hasattr(out, "content"):                                       # ToolMessage
        body = out.content
    return {"tools": names, "probe": {"tool": probe_name, **probe_summary(body)} if probe_name else None,
            "connection": "langchain.mcp.MCPAdapter({'mcpServers': {'omx': {command, args}}})"}


if __name__ == "__main__":
    run("langchain", ("langchain", "langchain-core", "langgraph", "fastmcp"), check)
