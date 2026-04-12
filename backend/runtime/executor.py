"""
FlowMind — Member 4: Agent & Orchestration
File: backend/runtime/executor.py

Workflow execution engine.

Responsibilities:
  • Iterate steps sequentially.
  • Detect approval gates → pause and set "waiting_approval" status.
  • Detect user-input gates → pause and set "waiting_user_input" status.
  • Route MCP-enabled tools through mcp_client.call_mcp_tool().
  • Route non-MCP tools through backend connector registry.
  • Chain data between steps (inject prior results into params).
  • Handle rollback on failure and set "failed_rolled_back" status.
  • Log every meaningful event via store.log_event().
"""

import logging

from backend.connectors.registry import get_connector
from backend.runtime import store
from backend.runtime.normalize import MCP_ENABLED_TOOLS

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data-chaining helpers
# ---------------------------------------------------------------------------

def _collect_prior_results(run: dict) -> dict:
    """
    Build a lookup of {tool: result_data} from all successfully completed steps.
    Used to inject upstream results into downstream step params.
    """
    prior: dict = {}
    for step in run["steps"]:
        if step.get("status") == "success" and step.get("result"):
            result = step["result"]
            if result.get("success"):
                prior[step["tool"]] = result.get("data", {})
    return prior


def _enrich_params(step: dict, prior: dict) -> dict:
    """
    Merge previous step results into the current step's params so connectors
    receive full context (e.g., Jira ticket ID in GitHub body).

    Rules:
      • github/create_issue → inject jira_ticket_id if available.
      • sheets/append_row   → inject all prior tool data into row_data.
      • email/send_email    → inject user_edited_params if set.
      • approval/request_user_input → pass through unchanged.
    """
    params = dict(step.get("params", {}))
    tool   = step["tool"]

    # Apply any user-edited params override (set by /submit-user-input endpoint)
    user_edited = step.get("user_edited_params")
    if user_edited and isinstance(user_edited, dict):
        params.update(user_edited)

    jira_data   = prior.get("jira",   {})
    github_data = prior.get("github", {})

    if tool == "github":
        jira_id = jira_data.get("ticket_id", "")
        if jira_id and "body" in params:
            params["body"] = params["body"].replace("JRA-?", jira_id)
        elif jira_id:
            params.setdefault("body", f"Linked to Jira ticket {jira_id}.")

    if tool == "sheets":
        row_data = params.get("row_data", {})
        if jira_data.get("ticket_id"):
            row_data.setdefault("jira_id", jira_data["ticket_id"])
        if github_data.get("issue_url"):
            row_data.setdefault("github_issue_url", github_data["issue_url"])
        if github_data.get("issue_id"):
            row_data.setdefault("github_issue_id", github_data["issue_id"])
        params["row_data"] = row_data

    return params


# ---------------------------------------------------------------------------
# Step dispatcher
# ---------------------------------------------------------------------------

def _dispatch_step(step: dict, params: dict) -> dict:
    """
    Route the step to either the real MCP client or the backend connector registry.

    Returns a standard result dict: {"success": bool, "message": str, "data": dict}
    """
    tool   = step["tool"]
    action = step["action"]

    if tool in MCP_ENABLED_TOOLS:
        # Attempt real MCP call; fall back to connector on failure
        try:
            from mcp_client import call_mcp_tool, is_mcp_available
            if is_mcp_available(tool):
                log.info("executor: routing '%s/%s' via MCP", tool, action)
                result = call_mcp_tool(tool, action, params)
                if result.get("success"):
                    return result
                # MCP failed — fall through to connector
                log.warning(
                    "executor: MCP call for '%s/%s' failed (%s) — falling back to connector",
                    tool, action, result.get("message"),
                )
            else:
                log.info(
                    "executor: MCP unavailable for '%s' — using connector fallback", tool
                )
        except ImportError:
            log.warning("executor: mcp_client not importable — using connector fallback")

    # --- Connector (REST / mock) fallback ---
    try:
        connector = get_connector(tool)
        log.info("executor: routing '%s/%s' via connector", tool, action)
        return connector.execute_action(action, params)
    except Exception as exc:
        log.error("executor: connector dispatch failed for '%s/%s': %s", tool, action, exc)
        return {
            "success": False,
            "message": f"Connector error for '{tool}/{action}': {exc}",
            "data": {},
        }


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------

def _attempt_rollback(run: dict) -> None:
    """
    Mark all already-completed steps as rolled back (best-effort).
    We only log the intent; no actual undo is performed for external systems.
    """
    run_id = run["run_id"]
    for step in run["steps"]:
        if step.get("status") == "success":
            store.update_step(run_id, step["step_id"], "rolled_back")
            store.log_event(run_id, step["step_id"], "info", "Step rolled back after downstream failure")


# ---------------------------------------------------------------------------
# Main execution engine
# ---------------------------------------------------------------------------

def execute_run(run: dict, start_from_step: str | None = None) -> None:
    """
    Execute the steps in *run* sequentially.

    Args:
        run:             The run dict from store.create_run() or store.get_run().
        start_from_step: If given, skip all steps before this step_id (used
                         when resuming after an approval or user-input gate).

    Behaviour:
      • Approval gate  → update status to "waiting_approval"  and return.
      • User-input gate → update status to "waiting_user_input" and return.
      • Step failure   → update run status to "failed_rolled_back" after rollback.
      • All done       → update run status to "completed".
    """
    run_id  = run["run_id"]
    started = start_from_step is None  # True means start from beginning

    store.update_run_status(run_id, "running")

    for step in run["steps"]:
        step_id = step["step_id"]

        # --- Fast-forward to resume point ---
        if not started:
            if step_id == start_from_step:
                started = True
            else:
                continue

        # --- Skip already-terminal steps ---
        if step["status"] in ("success", "failed", "rolled_back"):
            continue

        tool = step["tool"]

        # ----------------------------------------------------------------
        # APPROVAL GATE
        # ----------------------------------------------------------------
        if tool == "approval":
            store.update_step(run_id, step_id, "waiting_approval")
            store.update_run_status(run_id, "waiting_approval")
            store.log_event(run_id, step_id, "info",
                            "Workflow paused — awaiting human approval")
            return  # caller must hit POST /approve to resume

        # ----------------------------------------------------------------
        # USER-INPUT GATE
        # ----------------------------------------------------------------
        if tool == "request_user_input":
            store.update_step(run_id, step_id, "waiting_user_input")
            store.update_run_status(run_id, "waiting_user_input")
            question = step.get("params", {}).get("question", "Please provide input.")
            store.log_event(run_id, step_id, "info",
                            f"Workflow paused — awaiting user input: {question}")
            return  # caller must hit POST /submit-user-input to resume

        # ----------------------------------------------------------------
        # NORMAL TOOL EXECUTION
        # ----------------------------------------------------------------
        store.update_step(run_id, step_id, "running")
        store.log_event(run_id, step_id, "info", f"Starting step: {tool}/{step['action']}")

        prior  = _collect_prior_results(run)
        params = _enrich_params(step, prior)

        result = _dispatch_step(step, params)
        success = result.get("success", False)
        status  = "success" if success else "failed"

        store.update_step(run_id, step_id, status, result)
        store.log_event(
            run_id, step_id,
            "info" if success else "error",
            result.get("message", ""),
        )

        if not success:
            log.error("executor: step '%s' failed — beginning rollback", step_id)
            _attempt_rollback(run)
            store.update_run_status(run_id, "failed_rolled_back")
            return

    # All steps finished successfully
    store.update_run_status(run_id, "completed")
    store.log_event(run_id, "run", "info", "Workflow completed successfully")
    log.info("executor: run '%s' completed", run_id)
