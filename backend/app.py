"""FlowMind FastAPI backend – workflow execution endpoints."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.runtime.normalize import normalize_steps
from backend.runtime.store import create_run, get_run, update_step, update_run_status
from backend.runtime.executor import execute_run

app = FastAPI(title="FlowMind", description="Agentic MCP Gateway – MVP Runtime")

# Allow the frontend dev server to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request models ──────────────────────────────────────────────

class StepInput(BaseModel):
    tool: str
    input: str


class WorkflowRequest(BaseModel):
    steps: list[StepInput]


class ApproveRequest(BaseModel):
    run_id: str
    step_id: str


# ── Endpoints ───────────────────────────────────────────────────

@app.post("/execute-workflow")
def execute_workflow(req: WorkflowRequest):
    """Normalize LLM output, create a run, execute, and return state."""
    llm_output = {"steps": [s.model_dump() for s in req.steps]}
    tasks = normalize_steps(llm_output)
    run = create_run(tasks)
    execute_run(run)
    return run


@app.post("/approve-step")
def approve_step(req: ApproveRequest):
    """Approve a waiting step and resume execution."""
    run = get_run(req.run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{req.run_id}' not found")

    # Find the step
    step = next((s for s in run["steps"] if s["step_id"] == req.step_id), None)
    if not step:
        raise HTTPException(status_code=404, detail=f"Step '{req.step_id}' not found")
    if step["status"] != "waiting_approval":
        raise HTTPException(
            status_code=400,
            detail=f"Step '{req.step_id}' is not waiting for approval (status: {step['status']})",
        )

    # Mark approval step as success and resume
    update_step(req.run_id, req.step_id, "success", {
        "success": True,
        "message": "Approval granted",
        "data": {},
    })
    update_run_status(req.run_id, "running")

    # Resume from the step after the approved one
    step_ids = [s["step_id"] for s in run["steps"]]
    current_idx = step_ids.index(req.step_id)
    next_step_id = step_ids[current_idx + 1] if current_idx + 1 < len(step_ids) else None

    if next_step_id:
        execute_run(run, start_from_step=next_step_id)
    else:
        update_run_status(req.run_id, "completed")

    return run


@app.get("/run/{run_id}")
def get_run_status(run_id: str):
    """Return the current state of a run."""
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return run
