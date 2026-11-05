"""LangChain / LangGraph + OMX (Hyperliquid execution over MCP, stdio).

What it does: starts the OMX MCP server as a subprocess with `langchain.mcp.MCPAdapter` (the current
LangChain MCP API, `langchain[mcp]>=1.4`, built on FastMCP; it replaces the archived
`langchain-mcp-adapters`), loads its 9 tools as LangChain tools and runs a `create_agent` agent (a
LangGraph graph) that reads the limits, quotes ETH and previews (not submits) a small order.
verify/verify_langchain.py uses the same `omx_adapter()` without calling a model.

Install (versions this repo verified):
    pip install omx-hyperliquid==0.1.7 "langchain[mcp]==1.4.9" langchain-openai
Run (needs a model provider package and key; prompts go to the model):
    set LANGCHAIN_MODEL=openai:<model name>      (any "provider:model" string create_agent accepts)
    python examples/langchain_agent.py

Modes (OMX_MCP_ARGS): `--demo` (the default) runs the real OMX tools on a simulated venue inside the server
process: no key, account or network, no real orders possible, and every answer carries "demo": true.
`--inspect` only lists the tools; every call returns NOT_CONFIGURED.
Before real trading: run `omx --config omx.toml init --account 0xYOUR_MAIN_ADDRESS --key-path <agent key file>` once,
keep `omx --config omx.toml daemon` running in its own terminal, and set OMX_MCP_ARGS="--config omx.toml"
(this is exactly `omx-mcp --config omx.toml`; the server holds no key and forwards each call to the daemon).
Start on testnet.

- OMX is non-custodial: funds stay in your own Hyperliquid account; OMX signs only with an API/agent wallet that cannot withdraw.
- The agent orders only inside your limits: large or over-budget intents wait for human approval, and only a human can clear the kill switch.
- The 1 bp builder fee applies only after you approve it from your own wallet (`omx approve-builder`); `omx init --no-builder` sends none.
"""
from __future__ import annotations

import asyncio
import os

from langchain.agents import create_agent
from langchain.mcp import MCPAdapter

import omx_mcp


def omx_adapter() -> MCPAdapter:
    """The connection code shared with the verify script (an MCPConfig dict with one stdio server)."""
    return MCPAdapter({"mcpServers": {"omx": omx_mcp.stdio_config()}})


async def main() -> None:
    model = os.environ.get("LANGCHAIN_MODEL")
    if not model:
        raise SystemExit("set LANGCHAIN_MODEL, e.g. openai:<model name>")
    async with omx_adapter() as adapter:
        tools = await adapter.list_tools()
        agent = create_agent(model, tools, system_prompt=omx_mcp.AGENT_INSTRUCTIONS)
        result = await agent.ainvoke({"messages": [{"role": "user", "content": omx_mcp.DEMO_PROMPT}]})
        print(result["messages"][-1].content)


if __name__ == "__main__":
    asyncio.run(main())
