"""
FlowMind — Member 4: Agent & Orchestration
File: backend/runtime/normalize.py

Exposes: normalize_steps(), translate_agent_steps(),
         AGENT_TOOL_REMAP, MCP_ENABLED_TOOLS, TOOL_ACTION_MAP
"""

import logging

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool name mappings
# ---------------------------------------------------------------------------

# Maps LLM-produced tool names → backend canonical tool names
AGENT_TOOL_REMAP: dict[str, str] = {
    "create_jira_ticket":  "jira",
    "create_github_issue": "github",
    "update_google_sheet": "sheets",
    "send_email":          "email",
    "request_approval":    "approval",
    "request_user_input":  "request_user_input",
}

# Maps backend canonical tool names (and LLM aliases) → connector action strings
TOOL_ACTION_MAP: dict[str, str] = {
    # Canonical backend names
    "jira":               "create_ticket",
    "github":             "create_issue",
    "sheets":             "append_row",
    "email":              "send_email",
    "approval":           "request_approval",
    "request_user_input": "request_user_input",
    # LLM alias names (kept for safety when translation is skipped)
    "create_jira_ticket":  "create_ticket",
    "create_github_issue": "create_issue",
    "update_google_sheet": "append_row",
    "send_email":          "send_email",
    "request_approval":    "request_approval",
}

# Tools that use a real MCP server (Node.js stdio process) instead of REST
MCP_ENABLED_TOOLS: set[str] = {"github", "sheets", "email"}
# Jira is intentionally excluded — no reliable MCP server exists


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def translate_agent_steps(agent_output: dict) -> dict:
    """
    Remap every step's `tool` field from LLM names to backend canonical names.

    Args:
        agent_output: dict with shape {"steps": [{"tool": "...", "params": {...}}, ...]}

    Returns:
        New dict with the same shape but remapped tool names.
    """
    translated_steps = []
    for step in agent_output.get("steps", []):
        raw_tool = step.get("tool", "")
        canonical = AGENT_TOOL_REMAP.get(raw_tool, raw_tool)
        translated_steps.append({**step, "tool": canonical})
    return {"steps": translated_steps}


def normalize_steps(steps: list) -> list:
    """
    Convert a list of raw step dicts (from the LLM or agent) into the internal
    task format that `store.create_run()` and the executor expect.

    Accepts two flavours of input step:
      • New contract  → {"tool": "create_jira_ticket", "params": {"summary": "..."}}
      • Legacy contract → {"tool": "...", "input": "some string"}  (backward compat)

    For each step:
      1. Remap LLM tool name to backend canonical name via AGENT_TOOL_REMAP.
      2. Derive the connector action via TOOL_ACTION_MAP.
      3. Build a normalized step dict matching the store contract shape.
      4. Unknown tool → log a warning and skip (never crash).

    Returns:
        List of normalized step dicts:
        [
          {
            "step_id": "step_0",
            "tool": "jira",
            "action": "create_ticket",
            "params": {"summary": "...", ...},
            "requires_approval": False,
            "status": "pending",
            "result": None,
            "user_edited_params": None,
          },
          ...
        ]
    """
    normalized: list[dict] = []

    for idx, step in enumerate(steps):
        raw_tool = step.get("tool", "")

        # --- Step 1: Remap LLM alias → canonical backend name ---
        tool = AGENT_TOOL_REMAP.get(raw_tool, raw_tool)

        # --- Step 2: Derive action ---
        action = TOOL_ACTION_MAP.get(tool)
        if action is None:
            # Also try the un-remapped name as fallback
            action = TOOL_ACTION_MAP.get(raw_tool)

        if action is None:
            log.warning(
                "normalize_steps: unknown tool %r at index %d — skipping step",
                raw_tool, idx,
            )
            continue

        # --- Step 3: Extract params ---
        # New API uses "params" dict; legacy API used "input" string.
        if "params" in step and isinstance(step["params"], dict):
            params = dict(step["params"])
        else:
            # Legacy: wrap the raw "input" string so connectors still work
            params = {"raw_input": step.get("input", "")}

        # --- Step 4: Build normalized step matching store contract ---
        is_approval      = tool == "approval"
        is_user_input    = tool == "request_user_input"
        requires_approval = is_approval  # user_input gate is handled by the executor

        normalized.append({
            "step_id":            f"step_{idx}",
            "tool":               tool,
            "action":             action,
            "params":             params,
            "requires_approval":  requires_approval,
            "status":             "pending",
            "result":             None,
            "user_edited_params": None,
        })

    return normalized
