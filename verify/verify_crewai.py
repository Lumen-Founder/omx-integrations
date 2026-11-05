"""Verify the CrewAI (crewai_tools.MCPServerAdapter) connection to OMX without running a crew or a model."""
import asyncio

from _common import omx_mcp, probe_summary, run

from crewai_agent import omx_server_params
from crewai_tools import MCPServerAdapter


def _sync_check() -> dict:
    with MCPServerAdapter(omx_server_params(), connect_timeout=60) as tools:
        names = [t.name for t in tools]
        out = tools[omx_mcp.PROBE_TOOL].run(**omx_mcp.PROBE_ARGS) if omx_mcp.PROBE_TOOL in names else None
    return {"tools": names, "probe": {"tool": omx_mcp.PROBE_TOOL, **probe_summary(out)} if out is not None else None,
            "connection": "crewai_tools.MCPServerAdapter(mcp.StdioServerParameters(command, args))"}


async def check() -> dict:
    # MCPServerAdapter is synchronous and runs its own event loop, so keep it off ours.
    return await asyncio.to_thread(_sync_check)


if __name__ == "__main__":
    run("crewai", ("crewai", "crewai-tools", "mcpadapt"), check)
