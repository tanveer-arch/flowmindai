"""
FlowMind — Unified Backend (Members 1+2+3+4 Integrated)
File: backend/app.py

Endpoints:
  Auth (optional — works without Google creds):
    GET  /auth/google/login      → redirect to Google consent
    GET  /auth/google/callback   → OAuth callback
    GET  /auth/me                → current user
    POST /auth/logout            → logout

  Workflow (primary):
    POST /run-prompt             → NL prompt → LLM → execute (background thread)
    GET  /run/{run_id}           → poll run state (every 1–2s by frontend)
    POST /approve-step           → approve a waiting_approval gate
    POST /approve                → alias for /approve-step (backward compat)
    POST /submit-user-input      → supply user input for waiting_user_input gate
    GET  /runs                   → list all runs (history)
    GET  /logs/{run_id}          → execution logs for a run

  Misc:
    GET  /health                 → liveness probe

Response shape for /run-prompt (what Members2&3 frontend expects):
  {
    "run": {...},
    "prompt": "...",
    "generated_steps": [...]
  }
"""

import logging
import threading
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import generate_steps
from backend.runtime import store
from backend.runtime.executor import execute_run
from backend.runtime.normalize import normalize_steps

# ── Member 1: DB + Auth (fail-safe) ────────────────────────────
try:
    from backend.db.schema import init_db
    from backend.auth_routes import router as auth_router
    from backend.user_routes import router as user_router
    from backend.auth.dependencies import get_optional_user as _get_optional_user_db
    _M1_AVAILABLE = True
except ImportError:
    _M1_AVAILABLE = False

# ── Standalone auth (always available; in-memory sessions) ──────
try:
    from backend.auth import router as _standalone_auth_router
    from backend.auth import get_optional_user as _get_optional_user_standalone
    _STANDALONE_AUTH = True
except ImportError:
    _STANDALONE_AUTH = False
    log.warning("backend.auth package not available; auth features disabled")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: unified user extraction
# ---------------------------------------------------------------------------
def _get_user(request: Request) -> Optional[dict]:
    """Try DB-backed auth first, then standalone auth. Never raises."""
    if _M1_AVAILABLE:
        try:
            return _get_optional_user_db(request)
        except Exception:
            pass
    if _STANDALONE_AUTH:
        try:
            return _get_optional_user_standalone(request)
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="FlowMind",
    description="Agentic MCP Gateway — Unified Runtime",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://flowmindai-one.vercel.app",  # Production Vercel frontend
        "https://flowmindai-git-main-tanveer-archs-projects.vercel.app",  # Git branch URL
        "https://flowmindai-89f631f4c-tanveer-archs-projects.vercel.app", # User latest URL
    ],
    allow_origin_regex=r"https://flowmindai.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount routers ───────────────────────────────────────────────
if _M1_AVAILABLE:
    app.include_router(auth_router)
    app.include_router(user_router)

    @app.on_event("startup")
    def _startup_init_db():
        try:
            init_db()
        except Exception as exc:
            log.warning("DB init failed (non-fatal): %s", exc)

elif _STANDALONE_AUTH:
    # Use standalone auth when SQLite DB isn't available
    app.include_router(_standalone_auth_router)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class PromptRequest(BaseModel):
    prompt: str


class ApproveRequest(BaseModel):
    run_id: str
    step_id: Optional[str] = None  # optional — will find waiting step automatically


class UserInputRequest(BaseModel):
    run_id: str
    step_id: str
    # Accept either a plain string or a params dict (frontend sends params dict)
    user_input: Optional[str] = None
    params: Optional[dict] = None  # e.g. {"body": "Hello..."}


# ---------------------------------------------------------------------------
# Background execution helpers
# ---------------------------------------------------------------------------

def _execute_in_background(run: dict) -> None:
    """Execute in a daemon thread so HTTP response is immediate."""
    try:
        execute_run(run)
    except Exception as exc:
        log.error("Background executor crashed for run '%s': %s", run["run_id"], exc, exc_info=True)
        store.update_run_status(run["run_id"], "failed")


def _execute_in_background_from(run: dict, start_from_step: str) -> None:
    """Resume execution from a specific step."""
    try:
        execute_run(run, start_from_step=start_from_step)
    except Exception as exc:
        log.error(
            "Background executor crashed resuming run '%s' from '%s': %s",
            run["run_id"], start_from_step, exc, exc_info=True,
        )
        store.update_run_status(run["run_id"], "failed")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    """Lightweight liveness probe."""
    return {"status": "ok", "service": "FlowMind Agentic MCP Gateway"}


@app.post("/run-prompt")
def run_prompt(req: PromptRequest, request: Request):
    """
    Full pipeline: NL prompt → LLM → normalize → execute (background thread).

    Returns the Members2&3 frontend-compatible response shape:
      { "run": {...}, "prompt": "...", "generated_steps": [...] }

    The frontend immediately receives the run (status=pending/running) and
    polls /run/{run_id} for live updates.
    """
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    # Extract authenticated user (optional)
    user = _get_user(request)
    user_id = user["user_id"] if user else None

    # 1. LLM generates steps
    try:
        agent_output = generate_steps(prompt)
    except EnvironmentError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        log.error("generate_steps failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}")

    raw_steps = agent_output.get("steps", [])
    if not raw_steps:
        raise HTTPException(
            status_code=400,
            detail="The AI could not generate any executable steps for that prompt.",
        )

    # 2. Normalize steps
    tasks = normalize_steps(raw_steps)

    # 3. Create run record
    run = store.create_run(tasks, prompt, user_id=user_id)

    log.info("/run-prompt: created run '%s' with %d steps (user=%s)", run["run_id"], len(tasks), user_id)

    # 4. Execute in background thread
    thread = threading.Thread(target=_execute_in_background, args=(run,), daemon=True)
    thread.start()

    # 5. Return in shape the frontend expects
    return {
        "run": run,
        "prompt": prompt,
        "generated_steps": raw_steps,
    }


@app.get("/run/{run_id}")
def get_run(run_id: str):
    """Return the current state of a run. Called by frontend every 1-2 seconds."""
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return run


@app.post("/approve-step")
def approve_step(req: ApproveRequest):
    """
    Approve a workflow paused at a waiting_approval gate.
    Members2&3 frontend calls this endpoint by name.
    """
    run = store.get_run(req.run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{req.run_id}' not found")

    if run["status"] != "waiting_approval":
        raise HTTPException(
            status_code=400,
            detail=f"Run '{req.run_id}' is not awaiting approval (status: {run['status']})",
        )

    # Find the waiting approval step (by step_id if provided, else auto-find)
    if req.step_id:
        approval_step = next(
            (s for s in run["steps"] if s["step_id"] == req.step_id and s["status"] == "waiting_approval"),
            None,
        )
    else:
        approval_step = next(
            (s for s in run["steps"] if s["status"] == "waiting_approval"),
            None,
        )

    if not approval_step:
        raise HTTPException(status_code=400, detail="No step is currently waiting for approval")

    step_id = approval_step["step_id"]
    store.update_step(req.run_id, step_id, "success", {
        "success": True,
        "message": "Approval granted by user",
        "data": {},
    })
    store.log_event(req.run_id, step_id, "info", "Human approval granted")

    # Resume from next step
    step_ids = [s["step_id"] for s in run["steps"]]
    current_idx = step_ids.index(step_id)
    next_step = step_ids[current_idx + 1] if current_idx + 1 < len(step_ids) else None

    if next_step:
        thread = threading.Thread(
            target=_execute_in_background_from,
            args=(run, next_step),
            daemon=True,
        )
        thread.start()
    else:
        store.update_run_status(req.run_id, "completed")

    return store.get_run(req.run_id)


@app.post("/approve")
def approve(req: ApproveRequest):
    """Alias for /approve-step — backward compatibility with 1&4 backend."""
    return approve_step(req)


@app.post("/submit-user-input")
def submit_user_input(req: UserInputRequest):
    """
    Provide user input for a waiting_user_input gate.

    Accepts two formats (frontend sends 'params' dict, CLI sends 'user_input' string):
      - params: {"body": "Hello..."}  ← Members2&3 frontend format
      - user_input: "Hello..."        ← 1&4 backend format
    """
    run = store.get_run(req.run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{req.run_id}' not found")

    if run["status"] != "waiting_user_input":
        raise HTTPException(
            status_code=400,
            detail=f"Run '{req.run_id}' is not awaiting user input (status: {run['status']})",
        )

    waiting_step = next(
        (s for s in run["steps"] if s["step_id"] == req.step_id),
        None,
    )
    if not waiting_step:
        raise HTTPException(status_code=404, detail=f"Step '{req.step_id}' not found")
    if waiting_step["status"] != "waiting_user_input":
        raise HTTPException(status_code=400, detail=f"Step '{req.step_id}' is not waiting for user input")

    # Normalize input: merge both formats into user_edited_params
    if req.params:
        user_edited = req.params  # dict form from Members2&3 frontend
        input_text = req.params.get("body", req.params.get("user_input", str(req.params)))
    else:
        input_text = req.user_input or ""
        user_edited = {"user_input": input_text}

    store.update_step(req.run_id, req.step_id, "success", {
        "success": True,
        "message": "User input received",
        "data": user_edited,
    })
    waiting_step["user_edited_params"] = user_edited
    store.log_event(req.run_id, req.step_id, "info", f"User input received: {input_text[:100]}")

    # Resume from next step
    step_ids = [s["step_id"] for s in run["steps"]]
    current_idx = step_ids.index(req.step_id)
    next_step = step_ids[current_idx + 1] if current_idx + 1 < len(step_ids) else None

    if next_step:
        thread = threading.Thread(
            target=_execute_in_background_from,
            args=(run, next_step),
            daemon=True,
        )
        thread.start()
    else:
        store.update_run_status(req.run_id, "completed")

    return store.get_run(req.run_id)


@app.get("/runs")
def list_runs(request: Request):
    """List all workflow runs. Optionally filtered by authenticated user."""
    user = _get_user(request)
    user_id = user["user_id"] if user else ""
    return store.get_all_runs(user_id)


@app.get("/logs/{run_id}")
def get_run_logs(run_id: str):
    """Return all execution logs for a specific run."""
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return store.get_logs(run_id)
