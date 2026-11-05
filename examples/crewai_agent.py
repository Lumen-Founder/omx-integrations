"""CrewAI + OMX (Hyperliquid execution over MCP, stdio).

What it does: starts the OMX MCP server as a subprocess with `crewai_tools.MCPServerAdapter` and
`mcp.StdioServerParameters`, hands its 9 tools to a CrewAI `Agent`, and runs a one-task `Crew` that reads
the limits, quotes ETH and previews (not submits) a small order. verify/verify_crewai.py uses the same
`omx_server_params()` and lists/calls the tools without running the crew.

CrewAI pins `mcp<2` while OMX needs `mcp>=2.3`, so they cannot share one virtualenv. Install the OMX
server in one environment and CrewAI in another; point OMX_MCP_COMMAND at the server's executable
(MCP stdio talks over a pipe, so the two never import each other).

Install (versions this repo verified):
    python -m venv .venv          && .venv\\Scripts\\pip install omx-hyperliquid==0.1.3
    python -m venv .venv-crewai   && .venv-crewai\\Scripts\\pip install crewai==1.15.35 "crewai-tools[mcp]==1.15.35"
Run (needs a model key, e.g. OPENAI_API_KEY; prompts go to the model):
    set OMX_MCP_COMMAND=.venv\\Scripts\\omx-hyperliquid.exe
    .venv-crewai\\Scripts\\python examples/crewai_agent.py

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

from crewai import Agent, Crew, Task
from crewai_tools import MCPServerAdapter
from mcp import StdioServerParameters

import omx_mcp


def omx_server_params() -> StdioServerParameters:
    """The connection code shared with the verify script."""
    cfg = omx_mcp.stdio_config()
    return StdioServerParameters(command=cfg["command"], args=cfg["args"])


def main() -> None:
    with MCPServerAdapter(omx_server_params(), connect_timeout=60) as tools:
        trader = Agent(
            role="Execution agent",
            goal="Operate the user's Hyperliquid account through OMX, inside the limits OMX enforces.",
            backstory=omx_mcp.AGENT_INSTRUCTIONS,
            tools=tools,
        )
        task = Task(description=omx_mcp.DEMO_PROMPT, expected_output="A short summary of what OMX would do.",
                    agent=trader)
        print(Crew(agents=[trader], tasks=[task]).kickoff())


if __name__ == "__main__":
    main()
