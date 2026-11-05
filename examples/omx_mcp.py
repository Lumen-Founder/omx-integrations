"""How every example launches the OMX MCP server (stdio). Shared by examples/*_agent.py and verify/*.py.

OMX_MCP_COMMAND  the server executable. Default: `omx-hyperliquid` next to this Python
                 (same virtualenv), else the first one on PATH. `omx-hyperliquid` and `omx-mcp`
                 are the same entry point.
OMX_MCP_ARGS     the server arguments. Default: `--demo` (OMX >= 0.1.3): the real OMX tools on a
                 simulated venue inside the server process; no key, account, daemon or network, no
                 real orders, and every answer carries "demo": true.
                 `--inspect`: lists the 9 tools and refuses every call with NOT_CONFIGURED.
                 `--config omx.toml`: real use, through `omx daemon` (start on testnet).
                 Either a plain string (split on whitespace) or a JSON list,
                 e.g. ["--config", "C:\\path with spaces\\omx.toml"].

Nothing here reads a key. OMX never takes a key over MCP: the agent wallet key is read only by
`omx daemon`, from the key path in your omx.toml.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

DEFAULT_ARGS = "--demo"

# The 9 tools OMX 0.1.7 exposes over MCP. There is no tool to unkill, approve, or change limits, fees or keys.
EXPECTED_TOOLS = (
    "account_summary", "approval_status", "cancel_order", "get_quote", "kill_switch",
    "order_status", "policy_limits", "preview_order", "submit_order",
)

# A read-only market-data call, safe in every mode: a demo quote in --demo, NOT_CONFIGURED in --inspect.
PROBE_TOOL = "get_quote"
PROBE_ARGS = {"coin": "ETH"}

AGENT_INSTRUCTIONS = (
    "You operate a Hyperliquid account through OMX. Always call policy_limits first, then preview_order "
    "before submit_order, and pass a fresh client_intent_id on every submit. If a submit returns an "
    "approval_id, stop and tell the user a human must approve it. Trigger kill_switch if anything looks wrong."
)

DEMO_PROMPT = (
    "Read the OMX policy limits, get a quote for ETH, then preview (do not submit) a market buy of "
    "0.01 ETH and summarise what OMX would do and why."
)


def server_command() -> str:
    explicit = os.environ.get("OMX_MCP_COMMAND", "").strip()
    if explicit:
        return explicit
    exe = "omx-hyperliquid.exe" if os.name == "nt" else "omx-hyperliquid"
    local = Path(sys.executable).with_name(exe)
    if local.exists():
        return str(local)
    found = shutil.which("omx-hyperliquid")
    if found:
        return found
    raise RuntimeError("omx-hyperliquid not found: `pip install omx-hyperliquid==0.1.7` or set OMX_MCP_COMMAND")


def server_args() -> list[str]:
    raw = os.environ.get("OMX_MCP_ARGS", DEFAULT_ARGS).strip()
    if raw.startswith("["):
        args = json.loads(raw)
        if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
            raise ValueError("OMX_MCP_ARGS JSON must be a list of strings")
        return args
    return raw.split()


def mode() -> str:
    """inspect | demo | config | custom, for logs and the verify report."""
    args = server_args()
    if "--inspect" in args:
        return "inspect"
    if "--demo" in args:
        return "demo"
    if "--config" in args:
        return "config"
    return "custom"


def stdio_config() -> dict:
    """{"command": ..., "args": [...]}: the shape most MCP clients take for a stdio server."""
    return {"command": server_command(), "args": server_args()}
