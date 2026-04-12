# FlowMind V2 — Major Upgrade Implementation Plan

## Mentor Feedback Summary

The track mentor identified **10 critical upgrades** needed before final evaluation:

| # | Feedback Item | Priority |
|---|---|---|
| 1 | At least one tool fully dynamic (Email via SMTP) | 🔴 Critical |
| 2 | Real APIs for GitHub, Slack, Sheets (not mocked) | 🔴 Critical |
| 3 | Frontend ↔ Backend properly integrated | 🔴 Critical |
| 4 | Solve a real-world problem, not show mocked output | 🔴 Critical |
| 5 | Custom workflow — user can edit step params (e.g., email body) | 🟡 High |
| 6 | Rollback/restart on mid-execution errors | 🟡 High |
| 7 | Data passing between apps (cross-step context) | 🟡 High |
| 8 | Database + log files for RAG | 🟡 High |
| 9 | User authentication / login | 🟠 Medium |
| 10 | Voice-to-text for user prompt | 🟠 Medium |

---

## Team Assignment Overview (5 Members)

| Member | Role | Primary Tasks |
|--------|------|---------------|
| **Member 1** | Backend Infra Lead | Database (SQLite), logging, RAG, rollback/restart, auth endpoints |
| **Member 2** | API Connector Dev | Real GitHub, Slack, Sheets, Email (SMTP) connectors |
| **Member 3** | Frontend Dev | Full frontend-backend wiring, live execution UI, approval modal, step editor |
| **Member 4** | Agent & Orchestration Dev | LLM agent upgrades, user-interrupt flow, data chaining, voice-to-text |
| **Member 5** | Integration & QA Lead | Auth frontend (login page), end-to-end testing, demo prep, README |

---

## Detailed Task Breakdown

---

### 🟦 MEMBER 1 — Backend Infrastructure Lead

> **Focus:** Database, logs, RAG, rollback, authentication backend

#### Task 1.1: Replace in-memory store with SQLite database
**File:** `backend/runtime/store.py` → full rewrite

Currently `store.py` uses a Python dict (`_runs = {}`). Replace with SQLite so data persists across server restarts.

**Schema:**
```sql
-- Workflow runs
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    user_id TEXT,
    prompt TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Individual steps within a run
CREATE TABLE steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT REFERENCES runs(run_id),
    step_id TEXT,
    tool TEXT,
    action TEXT,
    params TEXT,           -- JSON string
    requires_approval BOOLEAN,
    status TEXT DEFAULT 'pending',
    result TEXT,           -- JSON string
    user_edited_params TEXT,  -- JSON string (if user customized this step)
    executed_at TIMESTAMP
);

-- Execution logs (for RAG)
CREATE TABLE execution_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT REFERENCES runs(run_id),
    step_id TEXT,
    level TEXT,            -- 'info', 'success', 'warning', 'error'
    message TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**What to do:**
- Create `backend/database.py` — SQLite connection, table creation, helper functions
- Rewrite `store.py` functions (`create_run`, `get_run`, `update_step`, `update_run_status`) to read/write from SQLite instead of the dict
- Add `log_event(run_id, step_id, level, message)` function for execution logs
- The database file should be `flowmind.db` in the project root

#### Task 1.2: Execution Logging
**File:** `backend/runtime/logger.py` (NEW)

Create a logging module that:
- Writes structured logs to the `execution_logs` SQLite table
- Also writes to a plain text log file (`logs/execution.log`) for debugging
- The executor should call `log_event()` before and after each step

#### Task 1.3: Rollback / Restart on Mid-Execution Error
**File:** `backend/runtime/executor.py` → modify `execute_run()`

Currently, when a step fails, the executor just sets status to `failed` and returns. Instead:

```python
def execute_run(run, start_from_step=None):
    """Execute with rollback support."""
    run_id = run["run_id"]
    max_retries = 2
    
    for step in run["steps"]:
        # ... skip logic same as before ...
        
        # Try executing with retries
        for attempt in range(1, max_retries + 1):
            result = dispatch(step["tool"], step["action"], params)
            if result.get("success"):
                store.update_step(run_id, step["step_id"], "success", result)
                log_event(run_id, step["step_id"], "success", result["message"])
                break
            else:
                log_event(run_id, step["step_id"], "warning", 
                         f"Attempt {attempt} failed: {result['message']}")
                if attempt == max_retries:
                    # Rollback: mark all previous successful steps as "rolled_back"
                    for prev_step in run["steps"]:
                        if prev_step["status"] == "success":
                            store.update_step(run_id, prev_step["step_id"], "rolled_back")
                    store.update_run_status(run_id, "failed_rolled_back")
                    log_event(run_id, step["step_id"], "error", "Max retries exceeded. Rollback executed.")
                    return
```

#### Task 1.4: RAG Endpoint (Simple version)
**File:** `backend/app.py` → add endpoint

Add a `GET /logs/{run_id}` endpoint that returns all execution logs for a run. This data feeds the "Learning Insights" panel on the frontend.

Add a `GET /history` endpoint that returns past workflow runs (for the RAG context — the LLM agent can use past successful runs to improve future suggestions).

#### Task 1.5: User Authentication Backend
**Files:** `backend/auth.py` (NEW), modify `backend/app.py`

Simple JWT-based auth:
- `POST /register` — username + password → create user in SQLite `users` table
- `POST /login` — username + password → return JWT token
- Add a `get_current_user()` dependency that validates the JWT on protected endpoints
- **Keep it simple:** use `python-jose` for JWT, `passlib` for password hashing

```
pip install python-jose[cryptography] passlib[bcrypt]
```

---

### 🟩 MEMBER 2 — API Connector Developer

> **Focus:** Replace ALL mock connectors with real API calls

#### Task 2.1: Real Email Connector (SMTP) — THE FULLY DYNAMIC ONE
**File:** `backend/connectors/email_connector.py` (NEW)

This is the **mandatory fully dynamic tool** the mentor wants. Use Python's built-in `smtplib` with Gmail SMTP (free, no API key needed — just an App Password).

```python
"""Email connector — sends real emails via Gmail SMTP."""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

def execute_action(action: str, params: dict) -> dict:
    if action == "send_email":
        sender = os.getenv("EMAIL_ADDRESS")       # Gmail address
        password = os.getenv("EMAIL_APP_PASSWORD") # Gmail App Password
        to = params.get("to", "")
        subject = params.get("subject", "FlowMind Notification")
        body = params.get("body", "")
        
        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        
        try:
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(sender, password)
                server.send_message(msg)
            return {
                "success": True,
                "message": f"Email sent to {to}",
                "data": {"to": to, "subject": subject}
            }
        except Exception as e:
            return {"success": False, "message": f"Email failed: {str(e)}", "data": {}}
    
    return {"success": False, "message": f"Unsupported action '{action}'", "data": {}}
```

**Setup needed (by the team member):**
1. Go to Google Account → Security → 2-Step Verification → App Passwords
2. Generate an App Password for "Mail"
3. Add to `.env`: `EMAIL_ADDRESS=your@gmail.com` and `EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx`

#### Task 2.2: Real GitHub Connector
**File:** `backend/connectors/github.py` → full rewrite

Use the GitHub REST API with a Personal Access Token (PAT).

```python
"""GitHub connector — creates real issues via GitHub REST API."""
import os
import requests

GITHUB_API = "https://api.github.com"
REPO = os.getenv("GITHUB_REPO", "ChaitanyaCodes55/FlowMind")  # owner/repo

def execute_action(action: str, params: dict) -> dict:
    token = os.getenv("GITHUB_TOKEN")
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    
    if action == "create_issue":
        title = params.get("title", "Untitled")
        body = params.get("body", "Created by FlowMind AI")
        resp = requests.post(
            f"{GITHUB_API}/repos/{REPO}/issues",
            headers=headers,
            json={"title": title, "body": body}
        )
        if resp.status_code == 201:
            data = resp.json()
            return {"success": True, "message": f"Issue #{data['number']} created", 
                    "data": {"issue_id": data["number"], "url": data["html_url"], "title": title}}
        return {"success": False, "message": f"GitHub API error: {resp.status_code} {resp.text}", "data": {}}
    
    return {"success": False, "message": f"Unsupported action '{action}'", "data": {}}
```

**Setup:** Create a GitHub PAT at github.com → Settings → Developer Settings → Personal Access Tokens. Add `GITHUB_TOKEN=ghp_xxx` to `.env`.

#### Task 2.3: Real Slack Connector
**File:** `backend/connectors/slack.py` → full rewrite

Use the Slack Incoming Webhook (simplest approach — no OAuth needed).

```python
"""Slack connector — sends real messages via Slack Incoming Webhook."""
import os
import requests

def execute_action(action: str, params: dict) -> dict:
    if action == "send_message":
        webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        text = params.get("text", "")
        channel = params.get("channel", "#general")
        
        resp = requests.post(webhook_url, json={
            "text": f"[FlowMind] {text}",
            "username": "FlowMind Bot"
        })
        if resp.status_code == 200:
            return {"success": True, "message": f"Slack message sent to {channel}", 
                    "data": {"channel": channel, "text": text}}
        return {"success": False, "message": f"Slack error: {resp.status_code}", "data": {}}
    
    return {"success": False, "message": f"Unsupported action '{action}'", "data": {}}
```

**Setup:** Create a Slack workspace (free) → Add "Incoming Webhooks" app → Copy webhook URL → Add `SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx` to `.env`.

#### Task 2.4: Real Google Sheets Connector
**File:** `backend/connectors/sheets.py` → full rewrite

Use `gspread` library with a Google Service Account.

```bash
pip install gspread
```

```python
"""Sheets connector — appends real rows via Google Sheets API."""
import os
import json
import gspread

def _get_client():
    creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS")  # path to service account JSON
    return gspread.service_account(filename=creds_json)

def execute_action(action: str, params: dict) -> dict:
    if action == "append_row":
        sheet_id = os.getenv("GOOGLE_SHEET_ID", "")
        sheet_name = params.get("sheet_name", "Sheet1")
        row_data = params.get("row_data", {})
        
        try:
            gc = _get_client()
            sh = gc.open_by_key(sheet_id)
            worksheet = sh.worksheet(sheet_name)
            worksheet.append_row(list(row_data.values()))
            return {"success": True, "message": f"Row appended to '{sheet_name}'",
                    "data": {"sheet_name": sheet_name, "row_data": row_data}}
        except Exception as e:
            return {"success": False, "message": f"Sheets error: {str(e)}", "data": {}}
    
    return {"success": False, "message": f"Unsupported action '{action}'", "data": {}}
```

**Setup:** Google Cloud Console → Create project → Enable Sheets API → Create Service Account → Download JSON key → Share the Google Sheet with the service account email.

#### Task 2.5: Update Registry
**File:** `backend/connectors/registry.py` → add email connector

```python
from backend.connectors import mock_pm, slack, github, sheets, email_connector

_REGISTRY = {
    "mock_pm": mock_pm,
    "slack": slack,
    "github": github,
    "sheets": sheets,
    "email": email_connector,   # NEW
}
```

#### Task 2.6: Update `.env.example` with all API keys

```env
GROQ_API_KEY=your_groq_key
GITHUB_TOKEN=ghp_your_github_pat
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx/xxx/xxx
GOOGLE_SHEET_ID=your_sheet_id
GOOGLE_SHEETS_CREDENTIALS=./google_creds.json
EMAIL_ADDRESS=your@gmail.com
EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
JWT_SECRET=your_random_secret_key
```

---

### 🟨 MEMBER 3 — Frontend Developer

> **Focus:** Wire frontend to real backend, live execution UI, approval modal, step editor

#### Task 3.1: Replace hardcoded simulation with real API calls
**File:** `frontend/app.js` → major rewrite of `generateWorkflow()`

The current `generateWorkflow()` picks a hardcoded template. Replace it with a real `fetch()` call:

```javascript
const API_BASE = "http://127.0.0.1:8080";

async function generateWorkflow() {
    const prompt = document.getElementById("promptInput").value.trim();
    if (!prompt || isGenerating) return;
    isGenerating = true;

    // 1. Send prompt to backend LLM endpoint
    const response = await fetch(`${API_BASE}/run-prompt`, {
        method: "POST",
        headers: { 
            "Content-Type": "application/json",
            "Authorization": `Bearer ${getToken()}`  // from auth
        },
        body: JSON.stringify({ prompt })
    });
    const data = await response.json();
    // data = { run_id, status, steps: [...] }

    // 2. Render the DAG from REAL steps
    renderDAGFromBackend(data.steps);
    renderToolsFromBackend(data.steps);

    // 3. If status is "waiting_user_input", show the step editor modal
    if (data.status === "waiting_user_input") {
        showStepEditorModal(data.run_id, data.steps);
        return;
    }
    
    // 4. If status is "waiting_approval", show approval modal
    if (data.status === "waiting_approval") {
        showApprovalModal(data.run_id, data.steps);
        return;
    }

    // 5. Poll for live updates
    pollRunStatus(data.run_id);
}
```

#### Task 3.2: Live Execution Polling
**File:** `frontend/app.js` → add polling function

```javascript
async function pollRunStatus(runId) {
    const interval = setInterval(async () => {
        const resp = await fetch(`${API_BASE}/run/${runId}`);
        const run = await resp.json();
        
        // Update DAG node status dots in real-time
        run.steps.forEach((step, i) => {
            updateNodeStatus(i, step.status);
            if (step.result) addLogEntry(step);
        });
        
        if (run.status === "completed" || run.status === "failed" || run.status === "failed_rolled_back") {
            clearInterval(interval);
            showLearningInsights(run);
        }
        if (run.status === "waiting_approval") {
            clearInterval(interval);
            showApprovalModal(runId, run.steps);
        }
    }, 1000); // poll every second
}
```

#### Task 3.3: Step Editor Modal (Custom Workflow)
**File:** `frontend/app.js` + `frontend/index.html` + `frontend/index.css`

When the executor hits a step that needs user input (like "what message should the email say?"), the frontend shows a modal:

```html
<!-- Add to index.html before </body> -->
<div id="stepEditorModal" class="modal hidden">
    <div class="modal-content">
        <h3>✏️ Customize This Step</h3>
        <p id="stepEditorPrompt">The system needs your input before continuing.</p>
        <textarea id="stepEditorInput" rows="4" placeholder="Type your custom message..."></textarea>
        <div class="modal-actions">
            <button onclick="submitStepEdit()" class="generate-btn">Submit & Continue</button>
            <button onclick="skipStepEdit()" class="feedback-btn">Use Default</button>
        </div>
    </div>
</div>
```

#### Task 3.4: Approval Modal
Similar to above but for approval gates. Shows a modal with "Approve" and "Reject" buttons.

#### Task 3.5: Login / Register Page
**File:** `frontend/login.html` + `frontend/login.js` (NEW)

Simple login page with username/password. On success, store the JWT in `localStorage` and redirect to `index.html`. All API calls in `app.js` should include the `Authorization: Bearer <token>` header.

#### Task 3.6: Voice-to-Text Button
**File:** `frontend/app.js` — add mic button + Web Speech API

```javascript
// Add a microphone button next to the Generate button
function startVoiceInput() {
    const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    recognition.lang = "en-US";
    recognition.onresult = (event) => {
        document.getElementById("promptInput").value = event.results[0][0].transcript;
    };
    recognition.start();
}
```

Add a 🎤 button in `index.html` next to the Generate button. This uses the **built-in browser API** — no external dependencies needed!

---

### 🟪 MEMBER 4 — Agent & Orchestration Developer

> **Focus:** Upgrade LLM agent, user-interrupt flow, data chaining, new tools in prompt

#### Task 4.1: Add Email Tool to the LLM Agent's System Prompt
**File:** `agent.py` → update `SYSTEM_PROMPT` and `valid_tools`

```python
SYSTEM_PROMPT = """You are FlowMind AI, a workflow automation engine.

AVAILABLE TOOLS (use ONLY these):
1. send_slack_message(message: string)   — sends a message to Slack
2. create_github_issue(title: string)    — creates a GitHub issue
3. update_google_sheet(data: string)     — adds/updates a row in Google Sheets
4. send_email(to: string, subject: string, body: string) — sends an email
5. request_approval(reason: string)      — pauses workflow for human approval
6. request_user_input(question: string)  — pauses to ask user for custom input

RULES:
- If the workflow involves sending an email, ALWAYS use request_user_input BEFORE
  send_email so the user can customize the email body.
- ...rest of existing rules...
"""
```

Also update `valid_tools` set to include `"send_email"`, `"request_approval"`, `"request_user_input"`.

#### Task 4.2: New Backend Endpoint — `/run-prompt`
**File:** `backend/app.py` → add new endpoint

This is the **key integration point** that connects the frontend to the LLM agent:

```python
class PromptRequest(BaseModel):
    prompt: str

@app.post("/run-prompt")
def run_prompt(req: PromptRequest):
    """Full pipeline: prompt → LLM → normalize → create run → execute → return."""
    from agent import generate_steps
    from backend.runtime.normalize import normalize_steps
    
    # 1. LLM generates steps
    agent_output = generate_steps(req.prompt)
    if not agent_output.get("steps"):
        raise HTTPException(status_code=400, detail="No steps generated")
    
    # 2. Translate agent tool names → backend tool names
    translated = translate_agent_steps(agent_output)
    
    # 3. Normalize into internal task format
    tasks = normalize_steps(translated)
    
    # 4. Create run and store original prompt
    run = create_run(tasks, prompt=req.prompt)
    
    # 5. Execute (will pause at approval/user_input gates)
    execute_run(run)
    
    return run
```

#### Task 4.3: User-Interrupt Flow (Custom Input Mid-Execution)
**File:** `backend/runtime/executor.py` → add `request_user_input` handling

When the executor hits a `request_user_input` step, it pauses (similar to approval):

```python
if step["tool"] == "request_user_input":
    store.update_step(run_id, step["step_id"], "waiting_user_input")
    store.update_run_status(run_id, "waiting_user_input")
    return  # pause — frontend will show the editor modal
```

Add a new endpoint `POST /submit-user-input`:
```python
@app.post("/submit-user-input")
def submit_user_input(req):
    """User provides custom input for a paused step. Resume execution."""
    # Save the user's custom input into the step's params
    # Resume execution from the next step
```

#### Task 4.4: Improved Data Chaining Between Steps
**File:** `backend/runtime/executor.py` → improve `_build_connector_params()`

Currently data chaining is hardcoded. Make it dynamic — each step result is stored and available to all subsequent steps:

```python
def _build_connector_params(step, run):
    """Build params dynamically from all prior step results."""
    # Collect ALL prior successful results into a context dict
    context = {}
    for s in run["steps"]:
        if s["result"] and s["result"].get("success"):
            context[s["tool"]] = s["result"].get("data", {})
    
    # Also include any user-edited params
    user_edits = step.get("user_edited_params", {})
    
    # Merge: raw_input + context + user_edits
    params = {"raw_input": step["params"].get("raw_input", ""), "context": context}
    params.update(user_edits)
    return params
```

#### Task 4.5: Update `normalize.py` — Add New Tools

Add `email`, `request_user_input` to `TOOL_ACTION_MAP` and `AGENT_TOOL_REMAP`:

```python
TOOL_ACTION_MAP = {
    "mock_pm": "get_issue",
    "slack": "send_message",
    "github": "create_issue",
    "sheets": "append_row",
    "email": "send_email",
    "approval": "request_approval",
    "request_user_input": "request_user_input",
    "send_email": "send_email",  # agent name
}

AGENT_TOOL_REMAP = {
    "send_slack_message": "slack",
    "create_github_issue": "github",
    "update_google_sheet": "sheets",
    "send_email": "email",
    "request_approval": "approval",
}
```

---

### 🟫 MEMBER 5 — Integration & QA Lead

> **Focus:** Login frontend, end-to-end testing, demo preparation, documentation

#### Task 5.1: Auth Frontend Polish
Work with Member 3 on `login.html` — make it match the FlowMind dark theme aesthetic. Add:
- Login form
- Register form (toggle between the two)
- Error messages for bad credentials
- Redirect to `index.html` on success

#### Task 5.2: End-to-End Testing Script
**File:** `test_e2e.py` (NEW)

Write a comprehensive test that:
1. Registers a test user → logs in → gets JWT
2. Sends a real prompt to `/run-prompt`
3. Polls `/run/{run_id}` until completion
4. Verifies that each connector was called
5. Checks that logs are stored in SQLite
6. Checks rollback works (simulate a failure)

#### Task 5.3: Setup All External Services
**This is a critical logistics task.** This person is responsible for:
- Creating a **free Slack workspace** and adding the Webhook
- Creating a **test GitHub repo** for issue creation
- Creating a **Google Sheet** and sharing it with the service account
- Creating a **Gmail App Password** for the email connector
- Filling in the real `.env` file with all the keys and testing each one individually

#### Task 5.4: Demo Preparation
- Prepare 3 demo workflows that showcase different tools
- Write the presentation talking points
- Record a backup video of the demo in case of network issues

#### Task 5.5: Update README and Documentation
Update `README.md` with:
- New project structure
- All environment variables needed
- How to set up each external service
- Screenshots of the working UI

---

## Execution Timeline

> [!IMPORTANT]
> Work in parallel! Members 1, 2, 3, 4 can all start at the same time since their tasks are in different files. Member 5 focuses on external service setup first, then testing.

### Hours 1-4: Foundation
| Member | Task |
|--------|------|
| 1 | SQLite database + rewrite store.py |
| 2 | Email connector (SMTP) + GitHub connector |
| 3 | Login page + auth frontend |
| 4 | Update agent.py system prompt + new `/run-prompt` endpoint |
| 5 | Set up Slack workspace + GitHub test repo + Google Sheet + Gmail App Password |

### Hours 5-8: Core Features
| Member | Task |
|--------|------|
| 1 | Logging + rollback/restart in executor |
| 2 | Slack connector + Sheets connector + update registry |
| 3 | Replace `generateWorkflow()` with real API fetch + DAG from backend |
| 4 | User-interrupt flow + data chaining |
| 5 | Fill `.env` with real keys + test each connector individually |

### Hours 9-12: Integration
| Member | Task |
|--------|------|
| 1 | RAG endpoint (`/history`, `/logs/{run_id}`) + auth middleware |
| 2 | Test all connectors end-to-end with real APIs |
| 3 | Step editor modal + approval modal + voice-to-text |
| 4 | Update normalize.py + test full LLM → backend pipeline |
| 5 | End-to-end testing script + bug fixes |

### Hours 13-16: Polish & Demo Prep
| All | Task |
|--------|------|
| Everyone | Run full demo end-to-end 3+ times. Fix bugs. Polish UI. Record backup video. |

---

## Updated `.env.example`

```env
# LLM Agent
GROQ_API_KEY=your_groq_api_key

# GitHub (create PAT at github.com/settings/tokens)
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
GITHUB_REPO=ChaitanyaCodes55/FlowMind

# Slack (create Incoming Webhook)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx/xxx/xxx

# Google Sheets (service account)
GOOGLE_SHEET_ID=your_google_sheet_id
GOOGLE_SHEETS_CREDENTIALS=./google_creds.json

# Email (Gmail SMTP)
EMAIL_ADDRESS=your@gmail.com
EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx

# Auth
JWT_SECRET=change_this_to_a_random_string
```

## Updated `requirements.txt`

```
fastapi>=0.100.0
uvicorn>=0.20.0
groq>=0.4.0
python-dotenv>=1.0.0
requests>=2.28.0
gspread>=6.0.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.0
```

## Open Questions

> [!IMPORTANT]
> 1. **Which email should we demo?** Sending to a teammate's email address live on stage is the most impressive demo. Decide who receives the email.
> 2. **Slack workspace:** Has anyone on the team already created a Slack workspace, or should we create a fresh one?
> 3. **GitHub repo:** Should we create issues on the FlowMind repo itself, or create a separate test repo?
