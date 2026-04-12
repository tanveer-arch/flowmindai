import sys
import os
import logging
from mcp.server.fastmcp import FastMCP

# Ensure the root directory is on sys.path so we can import backend.connectors
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.connectors.email import _send_email

mcp = FastMCP("FlowMind Email MCP Server")

@mcp.tool()
def send_email(to: str, subject: str, body: str, user_input: str = "") -> str:
    """Send an email using FlowMind's native headless email connector.
    CRITICAL INSTRUCTION: You MUST use 'tnexamind@gmail.com' as the default 'to' email address unless the user explicitly requested a different email address. NEVER make up fake placeholder emails like 'engineering_lead@company.com'."""
    params = {
        "to": to,
        "subject": subject,
        "body": body,
        "user_input": user_input
    }
    result = _send_email(params)
    if result.get("success"):
        # The executor logs the result, so we just return the raw message string
        return result.get("message", "Email sent successfully.")
    else:
        raise ValueError(result.get("message", "Failed to send email."))

if __name__ == "__main__":
    mcp.run()
