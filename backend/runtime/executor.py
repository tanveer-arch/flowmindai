"""Execution runtime – runs normalized steps sequentially via the connector registry."""

from backend.connectors.registry import dispatch
from backend.runtime import store


def _build_connector_params(step: dict, run: dict) -> dict:
    """Build params to pass to a connector based on tool type and prior step results.

    Enriches the raw_input with concrete values so the fake connectors
    receive the fields they expect.
    """
    tool = step["tool"]
    raw_input = step["params"].get("raw_input", "")

    # Gather results from earlier steps (for chaining data forward)
    prior_data: dict = {}
    for s in run["steps"]:
        if s["result"] and s["result"].get("success"):
            prior_data[s["tool"]] = s["result"].get("data", {})

    issue_data = prior_data.get("mock_pm", {})

    if tool == "mock_pm":
        return {"priority": "critical"}

    if tool == "slack":
        title = issue_data.get("title", "Critical issue")
        priority = issue_data.get("priority", "critical")
        return {
            "channel": "#alerts",
            "text": f"🚨 {title} [priority: {priority}] — {raw_input}",
        }

    if tool == "github":
        title = issue_data.get("title", "Follow-up issue")
        return {"title": f"Follow-up: {title}"}

    if tool == "sheets":
        return {
            "sheet_name": "Escalation Log",
            "row_data": {
                "issue_id": issue_data.get("id", "N/A"),
                "title": issue_data.get("title", "N/A"),
                "priority": issue_data.get("priority", "N/A"),
                "status": issue_data.get("status", "N/A"),
            },
        }

    # Fallback – just pass the raw input through
    return {"raw_input": raw_input}


def execute_run(run: dict, start_from_step: str | None = None):
    """Execute steps in order. Pauses on approval steps.

    If start_from_step is given, skip all steps before it.
    """
    run_id = run["run_id"]
    started = start_from_step is None  # if None, start from the beginning

    for step in run["steps"]:
        # Fast-forward to the resume point
        if not started:
            if step["step_id"] == start_from_step:
                started = True
            else:
                continue

        # Skip already-completed steps
        if step["status"] in ("success", "failed"):
            continue

        # --- Approval gate ---
        if step["requires_approval"]:
            store.update_step(run_id, step["step_id"], "waiting_approval")
            store.update_run_status(run_id, "waiting_approval")
            return  # pause execution

        # --- Normal tool execution ---
        store.update_step(run_id, step["step_id"], "running")
        params = _build_connector_params(step, run)
        result = dispatch(step["tool"], step["action"], params)
        status = "success" if result.get("success") else "failed"
        store.update_step(run_id, step["step_id"], status, result)

        if status == "failed":
            store.update_run_status(run_id, "failed")
            return

    # All steps done
    store.update_run_status(run_id, "completed")
