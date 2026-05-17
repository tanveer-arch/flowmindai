"""
FlowMind — Member 4: Agent & Orchestration
File: backend/runtime/normalize.py

Exposes: normalize_steps(), translate_agent_steps(), infer_dependencies(),
         AGENT_TOOL_REMAP, TOOL_ACTION_MAP

Phase 1: All tools execute via MCP. MCP_ENABLED_TOOLS removed.
Phase 2: Added depends_on field and infer_dependencies() for DAG execution.
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

# Maps backend canonical tool names (and LLM aliases) → MCP action strings
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

# Phase 1: All executable tools are MCP-backed. No MCP_ENABLED_TOOLS gate needed.
# Gate/control tools (approval, request_user_input) are handled by the executor directly.


# ---------------------------------------------------------------------------
# Phase 2: Dependency inference for DAG execution
# ---------------------------------------------------------------------------

# Known data-flow relationships between tools
_DATA_DEPENDENCIES: dict[str, set[str]] = {
    "github": {"jira"},             # GitHub body references Jira ticket_id
    "sheets": {"jira", "github"},   # Sheets row includes jira_id + github_issue_url
    "email":  set(),                # Email has no strict data dependency
    "jira":   set(),                # Jira has no upstream data dependency
}

# Gate tools that block all subsequent steps
_GATE_TOOLS: set[str] = {"approval", "request_user_input"}


def infer_dependencies(steps: list[dict]) -> None:
    """
    Populate the ``depends_on`` field for each step based on data-flow analysis.

    Rules:
      1. Gate tools (approval, request_user_input) depend on ALL prior steps.
      2. All steps AFTER a gate depend on that gate.
      3. Data dependencies: e.g., GitHub depends on Jira if Jira appears earlier.
      4. Steps with no dependencies can run in parallel.

    Mutates steps in-place.
    """
    tool_to_step_id: dict[str, str] = {}
    last_gate_id: str | None = None

    for i, step in enumerate(steps):
        step_id = step["step_id"]
        tool = step["tool"]
        deps: list[str] = []

        # Rule 2: If there was a gate before us, we depend on it
        if last_gate_id is not None:
            deps.append(last_gate_id)

        # Rule 1: Gate tools depend on ALL prior steps
        if tool in _GATE_TOOLS:
            deps = [s["step_id"] for s in steps[:i]]
            last_gate_id = step_id
        else:
            # Rule 3: Data dependencies from upstream tools
            data_deps = _DATA_DEPENDENCIES.get(tool, set())
            for dep_tool in data_deps:
                if dep_tool in tool_to_step_id:
                    dep_id = tool_to_step_id[dep_tool]
                    if dep_id not in deps:
                        deps.append(dep_id)

        step["depends_on"] = deps
        tool_to_step_id[tool] = step_id

    log.info(
        "infer_dependencies: %s",
        {s["step_id"]: s["depends_on"] for s in steps},
    )


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

    Phase 2: Each step now includes a ``depends_on`` list of step_ids, populated
    by ``infer_dependencies()``. The DAG executor uses this to run independent
    steps in parallel.
    """
    normalized: list[dict] = []

    for idx, step in enumerate(steps):
        raw_tool = step.get("tool", "")

        # --- Step 1: Remap LLM alias → canonical backend name ---
        tool = AGENT_TOOL_REMAP.get(raw_tool, raw_tool)

        # --- Step 2: Derive action ---
        action = TOOL_ACTION_MAP.get(tool)
        if action is None:
            action = TOOL_ACTION_MAP.get(raw_tool)

        if action is None:
            log.warning(
                "normalize_steps: unknown tool %r at index %d — skipping step",
                raw_tool, idx,
            )
            continue

        # --- Step 3: Extract params ---
        if "params" in step and isinstance(step["params"], dict):
            params = dict(step["params"])
        else:
            params = {"raw_input": step.get("input", "")}

        # --- Step 4: Build normalized step ---
        is_approval = tool == "approval"
        requires_approval = is_approval

        normalized.append({
            "step_id":            f"step_{idx}",
            "tool":               tool,
            "action":             action,
            "params":             params,
            "requires_approval":  requires_approval,
            "depends_on":         [],
            "status":             "pending",
            "result":             None,
            "user_edited_params": None,
        })

    # Phase 2: Infer step dependencies for DAG execution
    infer_dependencies(normalized)
    return normalized
