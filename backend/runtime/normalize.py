"""Normalization layer – converts raw LLM output into internal task list."""

# Fixed mapping from tool name to the action the connector expects.
TOOL_ACTION_MAP: dict[str, str] = {
    "mock_pm": "get_issue",
    "slack": "send_message",
    "github": "create_issue",
    "sheets": "append_row",
    "approval": "request_approval",
    # Agent-style names (fallback if translation is skipped)
    "send_slack_message": "send_message",
    "create_github_issue": "create_issue",
    "update_google_sheet": "append_row",
}

# Maps agent tool names to backend registry tool names
AGENT_TOOL_REMAP: dict[str, str] = {
    "send_slack_message": "slack",
    "create_github_issue": "github",
    "update_google_sheet": "sheets",
}


def normalize_steps(llm_output: dict) -> list[dict]:
    """Convert LLM step list into internal task format.

    Input shape:
        {"steps": [{"tool": "...", "input": "..."}, ...]}

    Output: list of normalized task dicts with sequential IDs.
    """
    raw_steps = llm_output.get("steps", [])
    tasks: list[dict] = []

    for idx, step in enumerate(raw_steps, start=1):
        tool = step.get("tool", "")
        # Remap agent-style names to backend names if needed
        tool = AGENT_TOOL_REMAP.get(tool, tool)
        action = TOOL_ACTION_MAP.get(tool, "unknown")
        is_approval = tool == "approval"

        tasks.append({
            "step_id": str(idx),
            "tool": tool,
            "action": action,
            "params": {"raw_input": step.get("input", "")},
            "requires_approval": is_approval,
            "status": "pending",
            "result": None,
        })

    return tasks
