import sys
import os
import logging
from mcp.server.fastmcp import FastMCP

# Ensure the root directory is on sys.path so we can import backend.connectors
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.connectors.sheets import _append_row

mcp = FastMCP("FlowMind Google Sheets MCP Server")

@mcp.tool()
def append_row(sheet_name: str, row_data: dict) -> str:
    """Append a row to Google Sheets using FlowMind's native headless sheets connector."""
    params = {
        "sheet_name": sheet_name,
        "row_data": row_data
    }
    result = _append_row(params)
    if result.get("success"):
        return result.get("message", "Row appended successfully.")
    else:
        raise ValueError(result.get("message", "Failed to append row."))

if __name__ == "__main__":
    mcp.run()
