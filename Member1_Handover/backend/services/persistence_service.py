"""Persistence hooks — save workflow, run, and step data to SQLite
alongside the existing in-memory store.

These hooks are called from ``backend/app.py`` AFTER the existing
runtime has done its work, so they cannot break the current flow.
All operations are wrapped in try/except to be fail-safe.
"""

import json
import logging
from typing import Optional

from backend.db.repositories import (
    save_workflow_template,
    save_workflow_run,
    save_workflow_step,
    update_step_status_db,
    update_run_status_db,
    get_run_by_runtime_id,
)
from backend.services.logging_service import log_event

logger = logging.getLogger("flowmind.persistence")


def persist_workflow(user_id: int | None, prompt: str,
                     generated_steps: list, run: dict) -> int | None:
    """Persist a complete workflow + run + steps to the database.

    Called AFTER ``run_prompt_workflow`` or ``execute_workflow`` succeeds.
    Returns the DB run ID, or None on failure.
    """
    if user_id is None:
        return None

    try:
        # 1. Save workflow template
        template_id = save_workflow_template(
            user_id=user_id,
            title=prompt[:80],
            original_prompt=prompt,
            generated_plan={"steps": generated_steps},
        )

        log_event("workflow_created",
                  f"Workflow template {template_id} created from prompt",
                  user_id=user_id, metadata={"template_id": template_id})

        # 2. Save the run
        runtime_run_id = run.get("run_id", "")
        db_run_id = save_workflow_run(
            user_id=user_id,
            runtime_run_id=runtime_run_id,
            input_prompt=prompt,
            workflow_template_id=template_id,
        )

        log_event("run_started",
                  f"Run {runtime_run_id} started (db_id={db_run_id})",
                  user_id=user_id, run_id=db_run_id)

        # 3. Save each step
        for idx, step in enumerate(run.get("steps", []), start=1):
            step_db_id = save_workflow_step(
                db_run_id=db_run_id,
                step_order=idx,
                runtime_step_id=step.get("step_id", ""),
                tool_name=step.get("tool", ""),
                action_name=step.get("action", ""),
                input_data=step.get("params", {}),
            )
            # Update step status from runtime
            status = step.get("status", "pending")
            result = step.get("result")
            update_step_status_db(db_run_id, step.get("step_id", ""),
                                  status, result)

            if status == "success":
                log_event("step_succeeded",
                          f"Step {step.get('step_id')} ({step.get('tool')}) succeeded",
                          user_id=user_id, run_id=db_run_id,
                          step_id=step_db_id)
            elif status == "failed":
                log_event("step_failed",
                          f"Step {step.get('step_id')} ({step.get('tool')}) failed",
                          user_id=user_id, run_id=db_run_id,
                          step_id=step_db_id, level="ERROR")

        # 4. Update run final status
        run_status = run.get("status", "running")
        update_run_status_db(db_run_id, run_status)

        if run_status == "completed":
            log_event("run_completed",
                      f"Run {runtime_run_id} completed successfully",
                      user_id=user_id, run_id=db_run_id)
        elif run_status == "failed":
            log_event("run_failed",
                      f"Run {runtime_run_id} failed",
                      user_id=user_id, run_id=db_run_id, level="ERROR")

        return db_run_id

    except Exception as exc:
        logger.warning("Failed to persist workflow data: %s", exc)
        return None
