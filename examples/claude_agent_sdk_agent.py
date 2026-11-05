"""Claude Agent SDK (Python) + OMX (Hyperliquid execution over MCP, stdio).

What it does: registers the OMX MCP server as a stdio server in `ClaudeAgentOptions.mcp_servers`; the
Claude Code runtime bundled with the SDK starts it as a subprocess. Read-only tools and preview_order
are pre-approved through `allowed_tools`; submit_order, cancel_order and kill_switch are not, so the
SDK's permission flow decides those. The agent reads the limits, quotes ETH and previews a small order.
verify/verify_claude_agent_sdk.py uses the same `omx_options()` and reads the server status and tool
list with `ClaudeSDKClient.get_mcp_status()` without sending a prompt.

(The Anthropic Messages API "MCP connector" takes remote URL servers only, so a local stdio server such
as OMX goes through the Agent SDK.)

Install (versions this repo verified):
    pip install omx-hyperliquid==0.1.3 claude-agent-sdk==0.2.178
Run (needs your own Anthropic credentials, e.g. ANTHROPIC_API_KEY; prompts go to the model):
    python examples/claude_agent_sdk_agent.py

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
from typing import Any

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query

import omx_mcp

SERVER = "omx"
READ_AND_PREVIEW = ("policy_limits", "get_quote", "account_summary", "order_status", "approval_status",
                    "preview_order")


def omx_options(**overrides: Any) -> ClaudeAgentOptions:
    """The connection code shared with the verify script."""
    opts: dict[str, Any] = dict(
        mcp_servers={SERVER: {"type": "stdio", **omx_mcp.stdio_config()}},
        allowed_tools=[f"mcp__{SERVER}__{t}" for t in READ_AND_PREVIEW],
        system_prompt=omx_mcp.AGENT_INSTRUCTIONS,
    )
    opts.update(overrides)
    return ClaudeAgentOptions(**opts)


async def main() -> None:
    async for message in query(prompt=omx_mcp.DEMO_PROMPT, options=omx_options()):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text)
        elif isinstance(message, ResultMessage):
            print(f"[done: {message.subtype}]")


if __name__ == "__main__":
    asyncio.run(main())
