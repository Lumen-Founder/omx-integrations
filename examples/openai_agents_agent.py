"""OpenAI Agents SDK + OMX (Hyperliquid execution over MCP, stdio).

What it does: starts the OMX MCP server as a subprocess with `agents.mcp.MCPServerStdio`, gives its
9 tools to an `Agent`, and asks it to read the policy limits, quote ETH and preview (not submit) a
small order. verify/verify_openai_agents.py uses the same `omx_server()` without calling a model.

Install (versions this repo verified):
    pip install omx-hyperliquid==0.1.3 openai-agents==0.24.0
Run (needs your own OPENAI_API_KEY; prompts go to the model):
    python examples/openai_agents_agent.py

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

from agents import Agent, Runner
from agents.mcp import MCPServerStdio

import omx_mcp


def omx_server() -> MCPServerStdio:
    """The connection code shared with the verify script."""
    return MCPServerStdio(
        name="omx",
        params=omx_mcp.stdio_config(),
        cache_tools_list=True,
        client_session_timeout_seconds=30,
    )


async def main() -> None:
    async with omx_server() as server:
        agent = Agent(name="OMX execution agent", instructions=omx_mcp.AGENT_INSTRUCTIONS, mcp_servers=[server])
        result = await Runner.run(agent, omx_mcp.DEMO_PROMPT)
        print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
