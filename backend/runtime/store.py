"""In-memory run store – tracks workflow runs and their step states."""

import uuid
from typing import Optional


# Module-level store: run_id -> run dict
_runs: dict[str, dict] = {}


def create_run(steps: list[dict]) -> dict:
    """Create a new workflow run with the given normalized steps."""
    run_id = str(uuid.uuid4())[:8]  # short ID for demo convenience
    run = {
        "run_id": run_id,
        "status": "running",
        "steps": steps,
    }
    _runs[run_id] = run
    return run


def get_run(run_id: str) -> Optional[dict]:
    """Return a run by ID, or None if not found."""
    return _runs.get(run_id)


def update_step(run_id: str, step_id: str, status: str, result: dict | None = None):
    """Update a specific step's status and result."""
    run = _runs.get(run_id)
    if not run:
        return
    for step in run["steps"]:
        if step["step_id"] == step_id:
            step["status"] = status
            if result is not None:
                step["result"] = result
            break


def update_run_status(run_id: str, status: str):
    """Update the overall run status."""
    run = _runs.get(run_id)
    if run:
        run["status"] = status
