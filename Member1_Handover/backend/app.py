"""FlowMind FastAPI backend workflow execution endpoints.

Existing endpoints are PRESERVED exactly as-is.
New additions:
  - DB initialization on startup
  - Auth & user-data routers mounted
  - Optional user-aware persistence hooks on existing endpoints
  - CORS credentials support for cookie-based auth
"""

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from backend.runtime.agent_runner import run_prompt_workflow
from backend.runtime.executor import execute_run
from backend.runtime.normalize import normalize_steps
from backend.runtime.store import create_run, get_run, update_run_status, update_step

# New imports for infrastructure layer
from backend.db.schema import init_db
from backend.auth.dependencies import get_optional_user
from backend.auth_routes import router as auth_router
from backend.user_routes import router as user_router
from backend.services.persistence_service import persist_workflow

app = FastAPI(title="FlowMind", description="Agentic MCP Gateway - MVP Runtime")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500", "http://localhost:5500"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,  # Added for cookie-based auth
)

# Mount new routers
app.include_router(auth_router)
app.include_router(user_router)


# ── Startup: initialize database ──────────────────────────────
@app.on_event("startup")
def on_startup():
    init_db()


# ── Pydantic models (UNCHANGED) ──────────────────────────────

class StepInput(BaseModel):
    tool: str
    input: str


class WorkflowRequest(BaseModel):
    steps: list[StepInput]


class PromptRequest(BaseModel):
    prompt: str


class ApproveRequest(BaseModel):
    run_id: str
    step_id: str


# ── Existing endpoints (PRESERVED — only persistence hooks added) ──

@app.post("/execute-workflow")
def execute_workflow(req: WorkflowRequest, request: Request):
    """Normalize structured steps, execute them, and return the run state."""
    llm_output = {"steps": [step.model_dump() for step in req.steps]}
    tasks = normalize_steps(llm_output)
    run = create_run(tasks)
    execute_run(run)

    # Persistence hook (safe, non-breaking)
    user = get_optional_user(request)
    if user:
        persist_workflow(
            user_id=user["user_id"],
            prompt="(structured workflow)",
            generated_steps=llm_output["steps"],
            run=run,
        )

    return run


@app.post("/run-prompt")
def run_prompt(req: PromptRequest, request: Request):
    """Generate a workflow from natural language and execute it."""
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    result = run_prompt_workflow(prompt)
    if not result["generated_steps"]:
        raise HTTPException(status_code=400, detail="No executable workflow steps could be generated")

    # Persistence hook (safe, non-breaking)
    user = get_optional_user(request)
    if user:
        persist_workflow(
            user_id=user["user_id"],
            prompt=prompt,
            generated_steps=result["generated_steps"],
            run=result["run"],
        )

    return result


@app.post("/approve-step")
def approve_step(req: ApproveRequest):
    """Approve a waiting step and resume execution."""
    run = get_run(req.run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{req.run_id}' not found")

    step = next((item for item in run["steps"] if item["step_id"] == req.step_id), None)
    if not step:
        raise HTTPException(status_code=404, detail=f"Step '{req.step_id}' not found")
    if step["status"] != "waiting_approval":
        raise HTTPException(
            status_code=400,
            detail=f"Step '{req.step_id}' is not waiting for approval (status: {step['status']})",
        )

    update_step(req.run_id, req.step_id, "success", {
        "success": True,
        "message": "Approval granted",
        "data": {},
    })
    update_run_status(req.run_id, "running")

    step_ids = [item["step_id"] for item in run["steps"]]
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
