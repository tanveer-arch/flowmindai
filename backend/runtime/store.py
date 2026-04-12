"""FlowMind — Unified In-Memory Run Store
File: backend/runtime/store.py

Public API:
  create_run(tasks, prompt, user_id=None) → dict
  get_run(run_id) → dict | None
  get_all_runs(user_id="") → list[dict]
  update_step(run_id, step_id, status, result=None)
  update_run_status(run_id, status)
  log_event(run_id, step_id, level, message)   ← used by executor
  add_log(run_id, step_id, level, message)     ← alias (Members2&3 compat)
  get_logs(run_id) → list[dict]
"""

import datetime
import logging
import uuid
from typing import Optional

_logger = logging.getLogger("flowmind.store")

# ── Member 1: DB persistence (fail-safe) ─────────────────────────
try:
    from backend.services.persistence_service import persist_workflow
    from backend.services.logging_service import log_event as _db_log_event
    from backend.db.repositories import (
        update_step_status_db,
        update_run_status_db,
        get_run_by_runtime_id,
    )
    _DB_AVAILABLE = True
except ImportError:
    _DB_AVAILABLE = False
    _logger.warning("Member 1 DB services not available — using in-memory only")

# ── In-memory stores ─────────────────────────────────────────────
_runs: dict[str, dict] = {}
_logs: dict[str, list[dict]] = {}


# ─────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────

def create_run(tasks: list, prompt: str = "", user_id=None) -> dict:
    """
    Create a new workflow run.

    Args:
        tasks:   Normalized step dicts from normalize_steps().
        prompt:  Original user prompt (stored for display).
        user_id: Authenticated user identifier (optional).

    Returns:
        Full run dict.
    """
    run_id = str(uuid.uuid4())[:8]
    run = {
        "run_id":     run_id,
        "prompt":     prompt,
        "status":     "pending",
        "user_id":    user_id,
        "steps":      tasks,
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
    }
    _runs[run_id] = run
    _logs[run_id] = []

    # Persist to SQLite (fail-safe)
    if _DB_AVAILABLE:
        try:
            persist_workflow(
                user_id=user_id,
                prompt=prompt,
                generated_steps=[s for s in tasks],
                run=run,
            )
        except Exception as exc:
            _logger.warning("DB persist_workflow failed (non-fatal): %s", exc)

    return run


def get_run(run_id: str) -> Optional[dict]:
    """Return a run by ID, or None."""
    return _runs.get(run_id)


def get_all_runs(user_id: str = "") -> list[dict]:
    """
    Return summary of all runs, optionally filtered by user_id.
    Returns newest first. Strips heavy step data for list view.
    """
    runs = list(_runs.values())
    if user_id:
        runs = [r for r in runs if str(r.get("user_id", "")) == str(user_id)]

    summaries = []
    for r in sorted(runs, key=lambda x: x.get("created_at", ""), reverse=True):
        summaries.append({
            "run_id":     r["run_id"],
            "status":     r["status"],
            "prompt":     r.get("prompt", ""),
            "num_steps":  len(r["steps"]),
            "created_at": r.get("created_at", ""),
        })
    return summaries


def update_step(
    run_id: str,
    step_id: str,
    status: str,
    result: Optional[dict] = None,
) -> None:
    """Update a specific step's status and optionally its result."""
    run = _runs.get(run_id)
    if not run:
        return
    for step in run["steps"]:
        if step["step_id"] == step_id:
            step["status"] = status
            if result is not None:
                step["result"] = result
            break

    # Sync to SQLite (fail-safe)
    if _DB_AVAILABLE:
        try:
            db_run = get_run_by_runtime_id(run_id)
            if db_run:
                update_step_status_db(db_run["id"], step_id, status, result)
        except Exception as exc:
            _logger.warning("DB update_step failed (non-fatal): %s", exc)


def update_run_status(run_id: str, status: str) -> None:
    """Update the overall run status."""
    run = _runs.get(run_id)
    if run:
        run["status"] = status
        if status in ("completed", "failed", "failed_rolled_back"):
            run["completed_at"] = datetime.datetime.utcnow().isoformat() + "Z"

    if _DB_AVAILABLE:
        try:
            db_run = get_run_by_runtime_id(run_id)
            if db_run:
                update_run_status_db(db_run["id"], status)
        except Exception as exc:
            _logger.warning("DB update_run_status failed (non-fatal): %s", exc)


def log_event(
    run_id: str,
    step_id: str,
    level: str,
    message: str,
) -> None:
    """
    Append a structured log entry for a run.
    Used by the executor. Persists to DB when available.
    """
    entry = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "step_id":   step_id,
        "level":     level,
        "message":   message,
    }
    if run_id in _logs:
        _logs[run_id].append(entry)

    if _DB_AVAILABLE:
        try:
            _db_log_event(
                event_type=f"step_{level.lower()}",
                message=message,
                level=level.upper(),
            )
        except Exception as exc:
            _logger.warning("DB log_event failed (non-fatal): %s", exc)


def add_log(run_id: str, step_id: str, level: str, message: str) -> None:
    """Alias for log_event — Members2&3 frontend compatibility."""
    log_event(run_id, step_id, level, message)


def get_logs(run_id: str) -> list[dict]:
    """Return all log entries for a run."""
    return _logs.get(run_id, [])
