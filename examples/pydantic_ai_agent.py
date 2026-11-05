"""PydanticAI + OMX (Hyperliquid execution over MCP, stdio).

What it does: wraps the OMX MCP server in `pydantic_ai.mcp.MCPToolset` over a FastMCP `StdioTransport`
(the current PydanticAI API; `MCPServerStdio` is the older name) and gives it to an `Agent` as a
toolset; the agent reads the limits, quotes ETH and previews (not submits) a small order.
verify/verify_pydantic_ai.py uses the same `omx_toolset()` and calls `list_tools()` /
`direct_call_tool()` without a model.

Install (versions this repo verified):
    pip install omx-hyperliquid==0.1.7 "pydantic-ai-slim[mcp,openai]==2.66.0"
Run (needs a model provider key; prompts go to the model):
    set PYDANTIC_AI_MODEL=openai:<model name>    (any "provider:model" string PydanticAI accepts)
    python examples/pydantic_ai_agent.py

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

from fastmcp.client.transports import StdioTransport
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset

import omx_mcp


def omx_toolset() -> MCPToolset:
    """The connection code shared with the verify script."""
    cfg = omx_mcp.stdio_config()
    return MCPToolset(StdioTransport(command=cfg["command"], args=cfg["args"]))


async def main() -> None:
    model = os.environ.get("PYDANTIC_AI_MODEL")
    if not model:
        raise SystemExit("set PYDANTIC_AI_MODEL, e.g. openai:<model name>")
    agent = Agent(model, instructions=omx_mcp.AGENT_INSTRUCTIONS, toolsets=[omx_toolset()])
    async with agent:
        result = await agent.run(omx_mcp.DEMO_PROMPT)
    print(result.output)


if __name__ == "__main__":
    asyncio.run(main())
