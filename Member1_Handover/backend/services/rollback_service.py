"""Rollback infrastructure for FlowMind.

Provides the groundwork for compensating / undoing workflow steps.
Not every connector supports rollback today, but the infrastructure
is ready for it.

Usage:
    # After a step succeeds, register its rollback data
    register_rollback(db_run_id, db_step_id, "github", result_data)

    # To rollback a full run
    execute_rollback(db_run_id)
"""

import logging
from backend.db.repositories import (
    save_rollback_action,
    get_rollback_actions_for_run,
    update_rollback_status,
)
from backend.services.logging_service import log_event

logger = logging.getLogger("flowmind.rollback")


# ──────────────────────────────────────────────────────────────
# Rollback Capability Registry
# ──────────────────────────────────────────────────────────────
# Maps tool_name -> rollback metadata builder.
# Each entry returns (action_type, payload_dict) or None if not
# reversible.

def _github_rollback_meta(result_data: dict):
    """GitHub issue creation can be reversed by closing the issue."""
    issue_id = result_data.get("data", {}).get("issue_id")
    if issue_id:
        return ("close_issue", {"issue_id": issue_id})
    return None


def _slack_rollback_meta(result_data: dict):
    """Slack messages can be deleted using the timestamp."""
    ts = result_data.get("data", {}).get("ts")
    channel = result_data.get("data", {}).get("channel")
    if ts and channel:
        return ("delete_message", {"channel": channel, "ts": ts})
    return None


def _sheets_rollback_meta(result_data: dict):
    """Sheets row append can be reversed by deleting the row."""
    row_index = result_data.get("data", {}).get("row_index")
    sheet_name = result_data.get("data", {}).get("sheet_name")
    if row_index and sheet_name:
        return ("delete_row", {"sheet_name": sheet_name, "row_index": row_index})
    return None


ROLLBACK_REGISTRY = {
    "github": _github_rollback_meta,
    "slack": _slack_rollback_meta,
    "sheets": _sheets_rollback_meta,
    # mock_pm has no rollback — read-only operation
}


# ──────────────────────────────────────────────────────────────
# Register Rollback
# ──────────────────────────────────────────────────────────────

def register_rollback(db_run_id: int, db_step_id: int,
                      tool_name: str, result_data: dict,
                      user_id: int | None = None):
    """Register rollback metadata for a successfully executed step.

    If the tool is not reversible or the result doesn't contain
    enough data, this is a no-op.
    """
    builder = ROLLBACK_REGISTRY.get(tool_name)
    if not builder:
        return

    meta = builder(result_data)
    if not meta:
        return

    action_type, payload = meta
    try:
        rb_id = save_rollback_action(
            db_run_id=db_run_id,
            db_step_id=db_step_id,
            tool_name=tool_name,
            rollback_action_type=action_type,
            rollback_payload=payload,
        )
        log_event("rollback_created",
                  f"Rollback action registered for {tool_name} (step {db_step_id})",
                  user_id=user_id, run_id=db_run_id, step_id=db_step_id,
                  metadata={"rollback_id": rb_id, "action_type": action_type})
    except Exception as exc:
        logger.warning("Failed to register rollback: %s", exc)


# ──────────────────────────────────────────────────────────────
# Execute Rollback
# ──────────────────────────────────────────────────────────────

def execute_rollback(db_run_id: int, user_id: int | None = None) -> list[dict]:
    """Execute all pending rollback actions for a run in REVERSE order.

    Returns a list of result dicts.
    """
    actions = get_rollback_actions_for_run(db_run_id)
    results = []

    for action in actions:
        if action["status"] != "pending":
            results.append({"id": action["id"], "status": "skipped",
                            "reason": f"Already {action['status']}"})
            continue

        tool = action["tool_name"]
        action_type = action["rollback_action_type"]

        try:
            # In a real system, we'd call the actual connector rollback.
            # For now, we simulate success and log it.
            logger.info("Executing rollback: %s.%s (id=%d)",
                        tool, action_type, action["id"])

            # Simulate rollback execution — in production this would call
            # connector-specific undo logic
            update_rollback_status(action["id"], "completed")
            log_event("rollback_executed",
                      f"Rollback {action_type} for {tool} completed",
                      user_id=user_id, run_id=db_run_id,
                      metadata={"rollback_id": action["id"]})
            results.append({"id": action["id"], "status": "completed",
                            "tool": tool, "action": action_type})

        except Exception as exc:
            logger.error("Rollback failed for action %d: %s",
                         action["id"], exc)
            update_rollback_status(action["id"], "failed")
            results.append({"id": action["id"], "status": "failed",
                            "error": str(exc)})

    return results
