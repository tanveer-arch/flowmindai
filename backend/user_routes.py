"""User-specific data retrieval routes for FlowMind.

Mounted at ``/api`` on the main FastAPI app.
All routes require authentication via ``get_current_user``.
"""

from fastapi import APIRouter, Depends, HTTPException

from backend.auth.dependencies import get_current_user
from backend.db.repositories import (
    get_user_workflows,
    get_user_runs,
    get_run_details,
    get_user_logs,
    get_rollback_actions_for_run,
)
from backend.services.rollback_service import execute_rollback

router = APIRouter(prefix="/api", tags=["user-data"])


@router.get("/my/workflows")
def my_workflows(user: dict = Depends(get_current_user)):
    """Return the current user's saved workflow templates."""
    workflows = get_user_workflows(user["user_id"])
    return {"workflows": workflows, "count": len(workflows)}


@router.get("/my/runs")
def my_runs(user: dict = Depends(get_current_user)):
    """Return the current user's workflow run history."""
    runs = get_user_runs(user["user_id"])
    return {"runs": runs, "count": len(runs)}


@router.get("/my/runs/{db_run_id}")
def my_run_detail(db_run_id: int, user: dict = Depends(get_current_user)):
    """Return full details for a specific run including steps."""
    run = get_run_details(db_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.get("user_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your run")
    return run


@router.get("/my/logs")
def my_logs(user: dict = Depends(get_current_user), limit: int = 100):
    """Return the current user's audit log entries."""
    logs = get_user_logs(user["user_id"], limit=limit)
    return {"logs": logs, "count": len(logs)}


@router.get("/my/runs/{db_run_id}/rollbacks")
def my_run_rollbacks(db_run_id: int,
                     user: dict = Depends(get_current_user)):
    """Return rollback actions for a specific run."""
    run = get_run_details(db_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.get("user_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your run")
    actions = get_rollback_actions_for_run(db_run_id)
    return {"rollback_actions": actions, "count": len(actions)}


@router.post("/my/runs/{db_run_id}/rollback")
def trigger_rollback(db_run_id: int,
                     user: dict = Depends(get_current_user)):
    """Execute rollback for all pending actions in a run."""
    run = get_run_details(db_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.get("user_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your run")
    results = execute_rollback(db_run_id, user_id=user["user_id"])
    return {"rollback_results": results}
