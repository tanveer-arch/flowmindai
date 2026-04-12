"""Persistent audit / event logging service for FlowMind.

Writes structured log entries into the ``execution_logs`` database table.
This is ADDITIVE — existing console logging is not modified.
"""

import logging
from backend.db.repositories import insert_log

logger = logging.getLogger("flowmind.audit")


def log_event(event_type: str, message: str,
              user_id: int | None = None,
              run_id: int | None = None,
              step_id: int | None = None,
              level: str = "INFO",
              metadata: dict | None = None):
    """Write a structured audit event to the database and to the console logger.

    Parameters
    ----------
    event_type : str
        One of: user_login, workflow_created, run_started, step_started,
        step_succeeded, step_failed, run_completed, run_failed,
        rollback_created, rollback_executed, etc.
    message : str
        Human-readable description.
    user_id, run_id, step_id : int | None
        Optional foreign keys for context.
    level : str
        Log level: INFO, WARNING, ERROR.
    metadata : dict | None
        Extra structured data to persist.
    """
    try:
        insert_log(
            user_id=user_id,
            run_id=run_id,
            step_id=step_id,
            log_level=level,
            event_type=event_type,
            message=message,
            metadata=metadata,
        )
    except Exception as exc:
        # Never let logging break the application
        logger.warning("Failed to persist audit log: %s", exc)

    # Also emit to standard logger for console visibility
    log_fn = getattr(logger, level.lower(), logger.info)
    log_fn("[%s] %s", event_type, message)
