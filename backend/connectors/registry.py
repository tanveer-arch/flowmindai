"""
FlowMind Connector Registry
File: backend/connectors/registry.py

Maps tool names → connector modules.
Each connector must expose: execute_action(action: str, params: dict) -> dict
"""

import logging

log = logging.getLogger(__name__)

# ── Core connectors (always available) ──────────────────────────
from backend.connectors import github, sheets, email

_REGISTRY: dict = {
    "github": github,
    "sheets": sheets,
    "email":  email,
}

# ── Optional connectors (fail-safe imports) ─────────────────────
try:
    from backend.connectors import jira as _jira
    _REGISTRY["jira"] = _jira
except ImportError:
    log.warning("jira connector not available")

try:
    from backend.connectors import mock_pm as _mock_pm
    _REGISTRY["mock_pm"] = _mock_pm
except ImportError:
    pass

try:
    from backend.connectors import slack as _slack
    _REGISTRY["slack"] = _slack
except ImportError:
    pass


# ── Public API ───────────────────────────────────────────────────

def get_available_tools() -> list[str]:
    """Return registered tool names."""
    return list(_REGISTRY.keys())


def get_connector(tool: str):
    """
    Return the connector module for *tool*.
    Raises KeyError if not registered.
    """
    connector = _REGISTRY.get(tool)
    if connector is None:
        raise KeyError(
            f"Unknown tool '{tool}'. Available: {get_available_tools()}"
        )
    return connector


def dispatch(tool: str, action: str, params: dict) -> dict:
    """
    Route a tool call to the correct connector.
    Returns a failure dict if the tool is not registered (never raises).
    """
    try:
        connector = get_connector(tool)
    except KeyError:
        return {
            "success": False,
            "message": f"Unknown tool '{tool}'. Available: {get_available_tools()}",
            "data": {},
        }
    try:
        return connector.execute_action(action, params)
    except Exception as exc:
        log.error("dispatch error for '%s/%s': %s", tool, action, exc, exc_info=True)
        return {
            "success": False,
            "message": f"Connector '{tool}' raised an exception: {exc}",
            "data": {},
        }
