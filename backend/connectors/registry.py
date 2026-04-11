"""Connector registry – maps tool names to their connector modules.

Usage from a future runtime:
    from backend.connectors.registry import dispatch
    result = dispatch("slack", "send_message", {"channel": "#alerts", "text": "Fire!"})
"""

from backend.connectors import mock_pm, slack, github, sheets

# Map of tool name → connector module.
# Each module exposes execute_action(action, params) -> dict.
_REGISTRY: dict = {
    "mock_pm": mock_pm,
    "slack": slack,
    "github": github,
    "sheets": sheets,
}


def get_available_tools() -> list[str]:
    """Return the list of registered tool names."""
    return list(_REGISTRY.keys())


def dispatch(tool: str, action: str, params: dict) -> dict:
    """Route a tool call to the correct connector.

    Returns a failure dict if the tool is not registered.
    """
    connector = _REGISTRY.get(tool)
    if connector is None:
        return {
            "success": False,
            "message": f"Unknown tool '{tool}'. Available: {get_available_tools()}",
            "data": {},
        }
    return connector.execute_action(action, params)
