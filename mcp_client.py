"""
FlowMind — Member 4: Agent & Orchestration
File: mcp_client.py

Exposes: call_mcp_tool(tool_name, action, params) -> dict
         is_mcp_available(tool_name) -> bool

This file handles ALL real MCP server communication.
MCP servers are launched on-demand as short-lived Node.js stdio processes.
"""

import asyncio
import logging
import os
import sys
import subprocess
from typing import Any

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MCP server configuration
# ---------------------------------------------------------------------------
# Each entry describes how to spawn the corresponding Node.js MCP server.
# Environment variables are merged with the current process env so that PATH
# and any existing vars are inherited (required for npx to work on Windows).

MCP_SERVER_CONFIGS: dict[str, dict] = {
    "github": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env_extra": {
            "GITHUB_PERSONAL_ACCESS_TOKEN": os.getenv("GITHUB_TOKEN", ""),
        },
    },
    "sheets": {
        "command": sys.executable,
        "args": ["-m", "backend.mcp_servers.mcp_sheets"],
        "env_extra": {},
    },
    "email": {
        "command": sys.executable,
        "args": ["-m", "backend.mcp_servers.mcp_email"],
        "env_extra": {},
    },
}

# Maps (canonical_tool, action) → exact MCP server tool name
TOOL_TO_MCP_NAME: dict[tuple[str, str], str] = {
    ("github", "create_issue"): "create_issue",
    ("sheets", "append_row"):   "append_row",
    ("email",  "send_email"):   "send_email",
}

# ---------------------------------------------------------------------------
# Availability cache — checked once per process lifetime
# ---------------------------------------------------------------------------
_availability_cache: dict[str, bool] = {}


def is_mcp_available(tool_name: str) -> bool:
    """
    Return True if the MCP server for *tool_name* could be started.

    Check order:
      1. In-memory cache (fastest — avoids repeated subprocess calls).
      2. Whether the tool has a known config entry.
      3. Whether `npx --version` succeeds (Node.js / npm in PATH).

    This intentionally does NOT actually start the MCP server — that happens
    lazily inside `call_mcp_tool()`.
    """
    if tool_name in _availability_cache:
        return _availability_cache[tool_name]

    if tool_name not in MCP_SERVER_CONFIGS:
        _availability_cache[tool_name] = False
        return False

    # Quick sanity-check: is the tool command available?
    command = MCP_SERVER_CONFIGS[tool_name]["command"]
    if command == "npx":
        try:
            result = subprocess.run(
                ["npx", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            available = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            available = False
    else:
        # sys.executable is inherently available
        available = True

    _availability_cache[tool_name] = available
    if not available:
        log.warning(
            "is_mcp_available: command '%s' not found or failed — MCP tool '%s' unavailable",
            command, tool_name,
        )
    return available


# ---------------------------------------------------------------------------
# Core async call — runs inside a dedicated event loop
# ---------------------------------------------------------------------------

async def _call_mcp_async(tool_name: str, mcp_tool_name: str, params: dict[str, Any]) -> dict:
    """
    Internal coroutine that actually spawns the MCP server process, initialises
    a ClientSession, calls the tool, and tears everything down.
    """
    # Import here so the module is importable even when mcp is not installed
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError:
        return {
            "success": False,
            "message": "mcp Python library is not installed. Run: pip install mcp",
            "data": {},
        }

    cfg = MCP_SERVER_CONFIGS[tool_name]
    env = {**os.environ, **cfg["env_extra"]}

    server_params = StdioServerParameters(
        command=cfg["command"],
        args=cfg["args"],
        env=env,
    )

    log.info("MCP: spawning '%s' server → tool '%s' with params %s", tool_name, mcp_tool_name, params)

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # Pre-process params for specific MCP servers
                if tool_name == "github" and mcp_tool_name == "create_issue":
                    gh_repo = os.getenv("GITHUB_REPO", "")
                    if "/" in gh_repo:
                        owner, name = gh_repo.split("/", 1)
                        params["owner"] = owner
                        params["repo"] = name
                        
                result = await session.call_tool(mcp_tool_name, params)

        # MCP result is a CallToolResult with a `content` list.
        # Extract the first text item if present.
        content_text = ""
        if hasattr(result, "content") and result.content:
            for item in result.content:
                if hasattr(item, "text"):
                    content_text = item.text
                    break

        log.info("MCP: '%s/%s' succeeded — raw=%s", tool_name, mcp_tool_name, content_text[:200])
        return {
            "success": True,
            "message": f"MCP tool '{mcp_tool_name}' executed successfully",
            "data": {"raw_output": content_text},
        }

    except Exception as exc:
        log.error("MCP: '%s/%s' failed — %s", tool_name, mcp_tool_name, exc, exc_info=True)
        return {
            "success": False,
            "message": f"MCP call failed: {exc}",
            "data": {},
        }


# ---------------------------------------------------------------------------
# Public synchronous interface
# ---------------------------------------------------------------------------

def call_mcp_tool(tool_name: str, action: str, params: dict[str, Any]) -> dict:
    """
    Synchronously call a real MCP server tool.

    Args:
        tool_name:  Canonical backend tool name ("github", "sheets", "email").
        action:     Backend action name ("create_issue", "append_row", "send_email").
        params:     Keyword params to pass to the MCP server tool.

    Returns:
        Standard connector result dict:
        {
            "success": True/False,
            "message": "...",
            "data": {...},
        }

    Flow:
      1. Resolve the exact MCP tool name from TOOL_TO_MCP_NAME.
      2. Run the async coroutine in a fresh (or running) event loop.
      3. Return the result dict.
    """
    # --- Resolve MCP tool name ---
    mcp_tool_name = TOOL_TO_MCP_NAME.get((tool_name, action))
    if mcp_tool_name is None:
        return {
            "success": False,
            "message": (
                f"No MCP mapping for tool='{tool_name}' action='{action}'. "
                f"Known: {list(TOOL_TO_MCP_NAME.keys())}"
            ),
            "data": {},
        }

    # --- Run async code synchronously ---
    try:
        # Python 3.10+: asyncio.run() always creates a fresh loop
        return asyncio.run(_call_mcp_async(tool_name, mcp_tool_name, params))
    except RuntimeError as exc:
        # In case an event loop is already running (e.g., Jupyter / some servers):
        # fall back to creating a new loop manually
        if "cannot run nested event loop" in str(exc).lower() or "event loop" in str(exc).lower():
            try:
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(
                        _call_mcp_async(tool_name, mcp_tool_name, params)
                    )
                finally:
                    loop.close()
            except Exception as inner:
                log.error("call_mcp_tool: nested-loop fallback also failed: %s", inner)
                return {
                    "success": False,
                    "message": f"Event loop error: {inner}",
                    "data": {},
                }
        raise
