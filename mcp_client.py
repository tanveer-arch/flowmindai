"""
FlowMind — Member 4: Agent & Orchestration
File: mcp_client.py

Exposes: call_mcp_tool(tool_name, action, params) -> dict
         dispatch_mcp(tool, action, params) -> dict   (for recovery engine)
         is_mcp_available(tool_name) -> bool

This file handles ALL real MCP server communication.
MCP servers are launched on-demand as short-lived Node.js/Python stdio processes.

Phase 1 changes:
  - Added 15s timeout per MCP call
  - Standardized response format with execution_time_ms
  - Added dispatch_mcp() entry point for recovery engine
  - Removed silent failure — MCP failure is a hard error
"""

import asyncio
import logging
import os
import sys
import subprocess
import time
from typing import Any

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Timeout configuration
# ---------------------------------------------------------------------------
MCP_CALL_TIMEOUT_SECONDS = 15

# ---------------------------------------------------------------------------
# MCP server configuration
# ---------------------------------------------------------------------------
# Each entry describes how to spawn the corresponding MCP server.
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
        "command": "npx",
        "args": ["-y", "@alanxchen/google-workspace-mcp"],
        "env_extra": {},
    },
    "email": {
        "command": "npx",
        "args": ["-y", "@gongrzhe/server-gmail-autoauth-mcp"],
        "env_extra": {},
    },
    "jira": {
        "command": "npx",
        "args": ["-y", "@aashari/mcp-server-atlassian-jira"],
        "env_extra": {
            "ATLASSIAN_SITE_NAME": os.getenv("JIRA_DOMAIN", "").replace(".atlassian.net", ""),
            "ATLASSIAN_USER_EMAIL": os.getenv("JIRA_EMAIL", ""),
            "ATLASSIAN_API_TOKEN": os.getenv("JIRA_API_TOKEN", ""),
        },
    },
}

# Maps (canonical_tool, action) → exact MCP server tool name
TOOL_TO_MCP_NAME: dict[tuple[str, str], str] = {
    ("github", "create_issue"): "create_issue",
    ("sheets", "append_row"):   "append_row",
    ("email",  "send_email"):   "send_email",
    ("jira",   "create_ticket"): "create_issue",
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
# Standard response builder
# ---------------------------------------------------------------------------

def _build_response(
    success: bool,
    message: str,
    data: dict | None = None,
    error_type: str | None = None,
    retryable: bool = False,
    execution_time_ms: float = 0,
) -> dict:
    """Build a standardized MCP response matching the PRD format."""
    resp: dict[str, Any] = {
        "success": success,
        "message": message,
        "data": data or {},
        "meta": {
            "execution_time_ms": round(execution_time_ms, 2),
        },
    }
    if not success:
        resp["error"] = {
            "type": error_type or "unknown_error",
            "message": message,
            "retryable": retryable,
        }
    return resp


# ---------------------------------------------------------------------------
# Core async call — runs inside a dedicated event loop
# ---------------------------------------------------------------------------

async def _call_mcp_async(tool_name: str, mcp_tool_name: str, params: dict[str, Any]) -> dict:
    """
    Internal coroutine that spawns the MCP server process, initialises
    a ClientSession, calls the tool, and tears everything down.
    Enforces a timeout of MCP_CALL_TIMEOUT_SECONDS.
    """
    start_time = time.monotonic()

    # Import here so the module is importable even when mcp is not installed
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError:
        return _build_response(
            success=False,
            message="mcp Python library is not installed. Run: pip install mcp",
            error_type="dependency_error",
            retryable=False,
        )

    cfg = MCP_SERVER_CONFIGS[tool_name]
    env = {**os.environ, **cfg["env_extra"]}

    server_params = StdioServerParameters(
        command=cfg["command"],
        args=cfg["args"],
        env=env,
    )

    log.info("MCP: spawning '%s' server → tool '%s' with params %s", tool_name, mcp_tool_name, params)

    try:
        async with asyncio.timeout(MCP_CALL_TIMEOUT_SECONDS):
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

        elapsed_ms = (time.monotonic() - start_time) * 1000
        log.info("MCP: '%s/%s' succeeded in %.0fms — raw=%s", tool_name, mcp_tool_name, elapsed_ms, content_text[:200])

        return _build_response(
            success=True,
            message=f"MCP tool '{mcp_tool_name}' executed successfully",
            data={"raw_output": content_text},
            execution_time_ms=elapsed_ms,
        )

    except TimeoutError:
        elapsed_ms = (time.monotonic() - start_time) * 1000
        log.error("MCP: '%s/%s' timed out after %ds", tool_name, mcp_tool_name, MCP_CALL_TIMEOUT_SECONDS)
        return _build_response(
            success=False,
            message=f"MCP call timed out after {MCP_CALL_TIMEOUT_SECONDS}s",
            error_type="timeout_error",
            retryable=True,
            execution_time_ms=elapsed_ms,
        )
    except Exception as exc:
        elapsed_ms = (time.monotonic() - start_time) * 1000
        log.error("MCP: '%s/%s' failed — %s", tool_name, mcp_tool_name, exc, exc_info=True)
        # Classify retryable errors
        err_str = str(exc).lower()
        retryable = any(kw in err_str for kw in ("timeout", "connection", "unavailable", "network"))
        return _build_response(
            success=False,
            message=f"MCP call failed: {exc}",
            error_type="execution_error",
            retryable=retryable,
            execution_time_ms=elapsed_ms,
        )


# ---------------------------------------------------------------------------
# Public synchronous interface
# ---------------------------------------------------------------------------

def call_mcp_tool(tool_name: str, action: str, params: dict[str, Any]) -> dict:
    """
    Synchronously call a real MCP server tool.

    Args:
        tool_name:  Canonical backend tool name ("github", "sheets", "email", "jira").
        action:     Backend action name ("create_issue", "append_row", "send_email").
        params:     Keyword params to pass to the MCP server tool.

    Returns:
        Standardized result dict:
        {
            "success": True/False,
            "message": "...",
            "data": {...},
            "meta": {"execution_time_ms": ...},
            "error": {...} | absent,
        }

    Phase 1: No fallback to connectors. MCP failure is a hard error.
    """
    # --- Resolve MCP tool name ---
    mcp_tool_name = TOOL_TO_MCP_NAME.get((tool_name, action))
    if mcp_tool_name is None:
        return _build_response(
            success=False,
            message=(
                f"No MCP mapping for tool='{tool_name}' action='{action}'. "
                f"Known: {list(TOOL_TO_MCP_NAME.keys())}"
            ),
            error_type="configuration_error",
            retryable=False,
        )

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
                return _build_response(
                    success=False,
                    message=f"Event loop error: {inner}",
                    error_type="runtime_error",
                    retryable=True,
                )
        raise


def dispatch_mcp(tool: str, action: str, params: dict[str, Any]) -> dict:
    """
    Unified MCP dispatch entry point for the recovery engine (sync).

    Replaces connectors.registry.dispatch() — same interface, MCP-backed.
    Returns standard {success, message, data} dict. Never raises.
    """
    if not is_mcp_available(tool):
        return _build_response(
            success=False,
            message=f"MCP server for '{tool}' is not available",
            error_type="unavailable_error",
            retryable=True,
        )

    try:
        return call_mcp_tool(tool, action, params)
    except Exception as exc:
        log.error("dispatch_mcp: unhandled error for '%s/%s': %s", tool, action, exc)
        return _build_response(
            success=False,
            message=f"MCP dispatch error: {exc}",
            error_type="runtime_error",
            retryable=False,
        )


# ---------------------------------------------------------------------------
# Public ASYNC interface (Phase 2 — used by async executor & DAG engine)
# ---------------------------------------------------------------------------

async def async_call_mcp_tool(tool_name: str, action: str, params: dict[str, Any]) -> dict:
    """
    Async version of call_mcp_tool. Primary interface for the async executor.

    Can be called directly from async code without event loop gymnastics.
    """
    mcp_tool_name = TOOL_TO_MCP_NAME.get((tool_name, action))
    if mcp_tool_name is None:
        return _build_response(
            success=False,
            message=(
                f"No MCP mapping for tool='{tool_name}' action='{action}'. "
                f"Known: {list(TOOL_TO_MCP_NAME.keys())}"
            ),
            error_type="configuration_error",
            retryable=False,
        )
    return await _call_mcp_async(tool_name, mcp_tool_name, params)


async def async_dispatch_mcp(tool: str, action: str, params: dict[str, Any]) -> dict:
    """
    Async version of dispatch_mcp. Used by async recovery engine and DAG executor.
    Never raises.
    """
    if not is_mcp_available(tool):
        return _build_response(
            success=False,
            message=f"MCP server for '{tool}' is not available",
            error_type="unavailable_error",
            retryable=True,
        )
    try:
        return await async_call_mcp_tool(tool, action, params)
    except Exception as exc:
        log.error("async_dispatch_mcp: unhandled error for '%s/%s': %s", tool, action, exc)
        return _build_response(
            success=False,
            message=f"MCP dispatch error: {exc}",
            error_type="runtime_error",
            retryable=False,
        )
