"""Shared plumbing for verify/verify_*.py. No LLM is called anywhere in verify/.

Each verify script connects to the OMX MCP server through the SAME function its example uses, lists the
tools, and (where the framework allows it without a model) calls the read-only `get_quote(coin="ETH")` once.
It prints one line `OMX_VERIFY_RESULT {json}` on stdout, which verify_all.py collects.
"""
from __future__ import annotations

import asyncio
import json
import platform
import sys
import time
import traceback
from importlib import metadata
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
sys.path.insert(0, str(EXAMPLES))

import omx_mcp  # noqa: E402

MARKER = "OMX_VERIFY_RESULT "


def versions(*dists: str) -> dict[str, Optional[str]]:
    out: dict[str, Optional[str]] = {}
    for d in dists:
        try:
            out[d] = metadata.version(d)
        except metadata.PackageNotFoundError:
            out[d] = None
    return out


def payload(obj: Any) -> Any:
    """Turn a framework's tool result into the OMX JSON dict when possible."""
    if isinstance(obj, (bytes, bytearray)):
        obj = obj.decode("utf-8", "replace")
    if isinstance(obj, str):
        try:
            return json.loads(obj)
        except ValueError:
            return obj
    return obj


def probe_summary(obj: Any) -> dict:
    p = payload(obj)
    if isinstance(p, dict):
        msg = p.get("message")
        out = {"parsed": True, "ok": p.get("ok"), "demo": p.get("demo"), "block_reasons": p.get("block_reasons"),
               "message": msg[:160] if isinstance(msg, str) else msg, "keys": sorted(p)[:20]}
        for k in ("coin", "best_bid", "best_ask", "mid"):
            if k in p:
                out[k] = p[k]
        return out
    return {"parsed": False, "raw": repr(p)[:300]}


def match_tools(names: list[str]) -> dict:
    """Map framework tool names (which may carry a server prefix) to the 9 OMX tool names."""
    found = {}
    for want in omx_mcp.EXPECTED_TOOLS:
        hit = [n for n in names if n == want or n.endswith("_" + want) or n.endswith("__" + want)]
        if hit:
            found[want] = hit[0]
    missing = [t for t in omx_mcp.EXPECTED_TOOLS if t not in found]
    return {"mapped": found, "missing": missing}


def probe_ok(probe: Optional[dict]) -> Optional[bool]:
    """--demo: the quote must succeed and be marked demo (ok=true, demo=true, a mid price).
    --inspect: the only correct answer is the refusal NOT_CONFIGURED. Otherwise any OMX answer dict counts."""
    if probe is None or probe.get("status") == "not_run":
        return None
    if not probe.get("parsed"):
        return False
    m = omx_mcp.mode()
    if m == "demo":
        return probe.get("ok") is True and probe.get("demo") is True and probe.get("mid") is not None
    if m == "inspect":
        return probe.get("ok") is False and "NOT_CONFIGURED" in (probe.get("block_reasons") or [])
    return isinstance(probe.get("block_reasons"), list)


def run(framework: str, dists: tuple[str, ...], check: Callable[[], Awaitable[dict]]) -> None:
    """check() returns {"tools": [names], "probe": probe_summary(...) | {"status": "not_run", ...}, ...}."""
    started = time.time()
    rec: dict[str, Any] = {
        "framework": framework, "python": platform.python_version(), "executable": sys.executable,
        "versions": versions(*dists, "omx-hyperliquid", "mcp"),
        "server": {"command": None, "args": None, "mode": None},
    }
    try:
        rec["server"] = {"command": omx_mcp.server_command(), "args": omx_mcp.server_args(), "mode": omx_mcp.mode()}
        got = asyncio.run(check())
        names = sorted(got.get("tools") or [])
        m = match_tools(names)
        rec.update(got)
        rec["tools"] = names
        rec["tool_count"] = len(names)
        rec["tools_missing"] = m["missing"]
        rec["probe_ok"] = probe_ok(got.get("probe"))
        tools_ok = not m["missing"] and len(names) == len(omx_mcp.EXPECTED_TOOLS)
        rec["status"] = "PASS" if tools_ok and rec["probe_ok"] is not False else "FAIL"
        if not tools_ok:
            rec["reason"] = f"expected the 9 OMX tools, got {len(names)}; missing {m['missing']}"
        elif rec["probe_ok"] is False:
            rec["reason"] = "probe tool call did not return the expected OMX answer"
    except BaseException as e:  # record, never hide
        rec["status"] = "FAIL"
        rec["reason"] = f"{type(e).__name__}: {e}"[:500]
        rec["traceback_tail"] = traceback.format_exc().splitlines()[-8:]
    rec["elapsed_s"] = round(time.time() - started, 2)
    print(MARKER + json.dumps(rec, default=str), flush=True)
    sys.exit(0 if rec["status"] == "PASS" else 1)
