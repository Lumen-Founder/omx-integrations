"""Run every verify/verify_*.py, write out/verify_results.json, and optionally refresh the README table.

    python verify_all.py                  # run all, write out/verify_results.json
    python verify_all.py --update-readme  # also rewrite the table between the README markers
    python verify_all.py --out out/verify_results_inspect.json   # with OMX_MCP_ARGS=--inspect

Each framework runs in its own subprocess with the interpreter that has that framework installed:
  OMX_VERIFY_PYTHON_<NAME>   e.g. OMX_VERIFY_PYTHON_CREWAI=.venv-crewai\\Scripts\\python.exe
Defaults: CrewAI uses .venv-crewai if it exists (CrewAI pins mcp<2, OMX needs mcp>=2.3, so the client
lives in a separate environment); every other framework uses the interpreter running this script.
OMX_MCP_COMMAND defaults to the omx-hyperliquid next to this interpreter, so a client in another
environment still starts the same OMX server. OMX_MCP_ARGS is passed through (default --demo; also
run it with OMX_MCP_ARGS=--inspect). No LLM is called.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "examples"))
import omx_mcp  # noqa: E402

OUT = ROOT / "out" / "verify_results.json"
README = ROOT / "README.md"
MARK_START, MARK_END = "<!-- verify-table:start -->", "<!-- verify-table:end -->"
MARKER = "OMX_VERIFY_RESULT "
BIN = "Scripts" if os.name == "nt" else "bin"
EXE = ".exe" if os.name == "nt" else ""

# (name, script, default interpreter, doc URL checked, how it connects)
FRAMEWORKS = [
    ("openai-agents", "verify_openai_agents.py", None,
     "https://openai.github.io/openai-agents-python/mcp/", "`agents.mcp.MCPServerStdio`"),
    ("langchain", "verify_langchain.py", None,
     "https://docs.langchain.com/oss/python/langchain/mcp", "`langchain.mcp.MCPAdapter` (MCPConfig dict)"),
    ("claude-agent-sdk", "verify_claude_agent_sdk.py", None,
     "https://code.claude.com/docs/en/agent-sdk/mcp", "`ClaudeAgentOptions(mcp_servers=...)` stdio"),
    ("pydantic-ai", "verify_pydantic_ai.py", None,
     "https://pydantic.dev/docs/ai/mcp/client/", "`pydantic_ai.mcp.MCPToolset` + FastMCP `StdioTransport`"),
    ("crewai", "verify_crewai.py", ROOT / ".venv-crewai" / BIN / f"python{EXE}",
     "https://docs.crewai.com/en/mcp/overview", "`crewai_tools.MCPServerAdapter` + `StdioServerParameters`"),
]
MAIN_PKG = {"openai-agents": "openai-agents", "langchain": "langchain", "claude-agent-sdk": "claude-agent-sdk",
            "pydantic-ai": "pydantic-ai-slim", "crewai": "crewai"}


def _version(dist: str) -> str | None:
    from importlib import metadata
    try:
        return metadata.version(dist)
    except metadata.PackageNotFoundError:
        return None


def interpreter(name: str, default: Path | None) -> Path:
    env = os.environ.get("OMX_VERIFY_PYTHON_" + name.upper().replace("-", "_"))
    if env:
        return Path(env)
    if default is not None and default.exists():
        return default
    return Path(sys.executable)


def run_one(name: str, script: str, default: Path | None, timeout_s: int) -> dict:
    py = interpreter(name, default)
    if not py.exists():
        return {"framework": name, "status": "FAIL", "reason": f"interpreter not found: {py}"}
    env = dict(os.environ)
    env.setdefault("OMX_MCP_COMMAND", str(Path(sys.executable).with_name(f"omx-hyperliquid{EXE}")))
    env.setdefault("OMX_MCP_ARGS", omx_mcp.DEFAULT_ARGS)
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [str(py), "-X", "utf8", "-B", str(ROOT / "verify" / script)]
    try:
        p = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return {"framework": name, "status": "FAIL", "reason": f"timeout after {timeout_s} s", "interpreter": str(py)}
    line = next((ln for ln in reversed(p.stdout.splitlines()) if ln.startswith(MARKER)), None)
    if line is None:
        tail = (p.stderr or p.stdout).strip().splitlines()[-6:]
        return {"framework": name, "status": "FAIL", "exit_code": p.returncode, "interpreter": str(py),
                "reason": "no result line; " + " | ".join(tail)[-500:]}
    rec = json.loads(line[len(MARKER):])
    rec["exit_code"] = p.returncode
    rec["interpreter"] = str(py)
    return rec


def cell_result(r: dict) -> str:
    if r.get("status") != "PASS":
        return f"FAIL: {r.get('reason', 'see JSON')}".replace("|", "/")[:160]
    probe = r.get("probe") or {}
    if probe.get("status") == "not_run":
        call = "tool call not possible without a model turn"
    elif probe.get("ok") is True:
        call = (f"`{probe.get('tool')}(coin=\"ETH\")` -> ok=true, demo={str(probe.get('demo')).lower()}, "
                f"mid {probe['mid']:.2f}" if isinstance(probe.get("mid"), (int, float)) else f"mid {probe.get('mid')}")
    else:
        call = f"`{probe.get('tool')}(coin=\"ETH\")` -> " + (", ".join(probe.get("block_reasons") or []) or "refused")
    return f"PASS: {r.get('tool_count')} tools listed; {call}"


def table(results: list[dict], meta: dict) -> str:
    by = {r["framework"]: r for r in results}
    rows = ["| Framework | Connection | Result (`OMX_MCP_ARGS=" + " ".join(meta["omx_mcp_args"]) + "`) "
            "| Verified versions | Docs checked |", "|---|---|---|---|---|"]
    for name, _s, _d, url, conn in FRAMEWORKS:
        r = by.get(name, {"status": "FAIL", "reason": "not run"})
        v = r.get("versions") or {}
        vers = ", ".join(f"{k} {val}" for k, val in v.items() if val) or "-"
        rows.append(f"| {name} | {conn} | {cell_result(r)} | {vers} | [docs]({url}) |")
    rows.append("")
    rows.append(f"Generated by `verify_all.py` at {meta['generated_at']} on {meta['platform']}; OMX server: "
                f"omx-hyperliquid {meta['omx_hyperliquid_version_server_env']} (PyPI) with mcp "
                f"{meta['mcp_version_server_env']} for every row; evidence: `out/verify_results.json`.")
    return "\n".join(rows)


def update_readme(text_table: str) -> bool:
    if not README.exists():
        return False
    s = README.read_text(encoding="utf-8")
    a, b = s.find(MARK_START), s.find(MARK_END)
    if a < 0 or b < a:
        return False
    README.write_text(s[:a + len(MARK_START)] + "\n" + text_table + "\n" + s[b:], encoding="utf-8")
    return True


def _relative_paths(text: str) -> str:
    """Write paths under this checkout as `.` so the evidence names no local directory."""
    for root in (str(ROOT), ROOT.as_posix()):
        text = text.replace(json.dumps(root)[1:-1], ".")
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--update-readme", action="store_true")
    ap.add_argument("--only", nargs="*", help="framework names to run")
    ap.add_argument("--timeout-s", type=int, default=180)
    ap.add_argument("--out", type=Path, default=OUT, help="result JSON path (default out/verify_results.json)")
    ns = ap.parse_args()
    out_path = ns.out if ns.out.is_absolute() else ROOT / ns.out
    results = []
    for name, script, default, _url, _conn in FRAMEWORKS:
        if ns.only and name not in ns.only:
            continue
        print(f"[verify] {name} ...", flush=True)
        r = run_one(name, script, default, ns.timeout_s)
        results.append(r)
        print(f"[verify] {name}: {cell_result(r)}", flush=True)
    meta = {
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platform": f"{platform.system()} {platform.release()}, Python {platform.python_version()}",
        "omx_mcp_command": os.environ.get("OMX_MCP_COMMAND") or str(Path(sys.executable).with_name(f"omx-hyperliquid{EXE}")),
        "omx_mcp_args": omx_mcp.server_args(),
        "omx_hyperliquid_version_server_env": _version("omx-hyperliquid"),
        "mcp_version_server_env": _version("mcp"),
        "llm_called": False,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"meta": meta, "summary": {r["framework"]: r.get("status") for r in results}, "results": results}
    out_path.write_text(_relative_paths(json.dumps(doc, indent=2, default=str)) + "\n", encoding="utf-8")
    print(f"[verify] wrote {out_path.relative_to(ROOT) if out_path.is_relative_to(ROOT) else out_path}")
    if ns.update_readme:
        print("[verify] README table " + ("updated" if update_readme(table(results, meta)) else "markers not found"))
    passed = sum(r.get("status") == "PASS" for r in results)
    print(f"[verify] {passed}/{len(results)} PASS")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
