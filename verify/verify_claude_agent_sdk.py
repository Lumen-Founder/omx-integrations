"""Verify the Claude Agent SDK connection to OMX without sending a prompt (no model call).

ClaudeSDKClient.connect() with no prompt starts the bundled Claude Code runtime, which starts the OMX stdio
server; get_mcp_status() then reports the server status and its tool list. The SDK has no way to call an MCP
tool without a model turn, so the probe call is recorded as not_run.

Isolation: setting_sources=[] (no user/project/local settings), a throwaway cwd and CLAUDE_CONFIG_DIR under
out/claude_cwd, so the run neither reads nor writes this machine's Claude settings or credentials.
"""
import asyncio
from pathlib import Path

from _common import omx_mcp, run

from claude_agent_sdk import ClaudeSDKClient
from claude_agent_sdk_agent import SERVER, omx_options

SCRATCH = Path(__file__).resolve().parents[1] / "out" / "claude_cwd"


async def check() -> dict:
    (SCRATCH / "config").mkdir(parents=True, exist_ok=True)
    opts = omx_options(
        cwd=str(SCRATCH),
        setting_sources=[],
        env={"CLAUDE_CONFIG_DIR": str(SCRATCH / "config"), "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"},
    )
    entry: dict = {}
    history = []
    async with ClaudeSDKClient(options=opts) as client:
        for _ in range(60):                       # up to ~30 s for the stdio server to connect
            status = await client.get_mcp_status()
            entry = next((s for s in status.get("mcpServers", []) if s.get("name") == SERVER), {})
            if not history or history[-1] != entry.get("status"):
                history.append(entry.get("status"))
            if entry.get("status") in ("connected", "failed", "needs-auth", "disabled"):
                break
            await asyncio.sleep(0.5)
    tools = [t.get("name") if isinstance(t, dict) else str(t) for t in (entry.get("tools") or [])]
    return {
        "tools": tools,
        "probe": {"status": "not_run", "reason": "the SDK calls MCP tools only inside a model turn"},
        "mcp_status": entry.get("status"), "mcp_status_history": history,
        "server_info": entry.get("serverInfo"), "mcp_error": entry.get("error"),
        "connection": "ClaudeAgentOptions(mcp_servers={'omx': {type: stdio, command, args}}) + get_mcp_status()",
    }


if __name__ == "__main__":
    run("claude-agent-sdk", ("claude-agent-sdk",), check)
