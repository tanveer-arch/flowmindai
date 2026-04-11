# FlowMind AI

FlowMind AI is a self-evolving agentic workflow orchestration system that converts natural language instructions into executable multi-step workflows. It uses LLM-driven planning, contextual memory, and adaptive learning to automate tasks across platforms through an MCP-oriented integration layer.

## Problem Statement

Modern workflows are spread across multiple platforms such as GitHub, Slack, Google Sheets, and internal tools. Managing these manually creates delays, fragmentation, and repetitive work.

FlowMind AI addresses this by:
- understanding user intent from natural language
- generating structured workflows
- executing tasks across multiple tools
- collecting execution feedback
- improving future workflow performance over time

## Core Idea

FlowMind AI acts as an intelligent orchestration layer that:

- interprets natural language into workflow steps
- generates an execution plan in the form of a DAG
- routes each task to the appropriate tool through an MCP-style gateway
- tracks execution history and user feedback
- adapts workflows for better future performance

## Key Features

### 1. Natural Language to Workflow
Users can describe a task in plain language, and the system converts it into structured executable steps.

Example:
> "When a critical GitHub bug is created, notify the engineering team on Slack, update the escalation tracker, and request manager approval."

### 2. Agentic Workflow Planning
The system uses LLM-based reasoning to break down user intent into tasks, dependencies, and execution order.

### 3. MCP-Oriented Cross-Platform Integration
FlowMind AI connects different tools through a unified orchestration layer. For the prototype, this includes integrations such as:
- GitHub
- Slack
- Google Sheets

### 4. Execution Engine
The generated workflow is executed step by step, with support for retries, status tracking, and human-in-the-loop approvals for sensitive operations.

### 5. Feedback-Driven Learning
Execution results are stored and used to refine later workflow suggestions, tool selection, and sequencing.

### 6. Explainability and Control
The system provides visibility into:
- why a workflow was generated
- which tools were selected
- where failures occurred
- when approvals are required

---

## Project Structure

```
FlowMind/
├── backend/                    # FastAPI backend
│   ├── app.py                  # API endpoints (execute, approve, status)
│   ├── connectors/             # Fake tool connectors (mock_pm, slack, github, sheets)
│   │   └── registry.py         # Dispatcher: tool name → connector
│   └── runtime/
│       ├── normalize.py        # LLM output → internal task list
│       ├── executor.py         # Sequential step runner with approval gates
│       ├── store.py            # In-memory run state tracking
│       └── agent_runner.py     # Bridges LLM agent → backend executor
├── frontend/                   # Static frontend UI
│   ├── index.html
│   ├── index.css
│   └── app.js
├── docs/                       # Hackathon documents
├── agent.py                    # LLM agent brain (Groq / Llama 3.3)
├── requirements.txt
├── .env.example
└── smoke_test.py               # API smoke test
```

## How to Run

### Prerequisites

```bash
pip install -r requirements.txt
```

Copy the environment template and add your Groq API key (only needed for the LLM agent, not for the backend):

```bash
cp .env.example .env
# Edit .env and set GROQ_API_KEY=your_key_here
```

### Start the Backend

```bash
python -m uvicorn backend.app:app --reload --port 8000
```

Backend will be available at: **http://localhost:8000**

API docs (Swagger): **http://localhost:8000/docs**

### Start the Frontend

```bash
python -m http.server 5500 --directory frontend
```

Frontend will be available at: **http://localhost:5500**

### Run the Smoke Test

With the backend running on port 8000:

```bash
python smoke_test.py
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/execute-workflow` | Submit LLM steps for execution |
| `POST` | `/approve-step` | Approve a paused approval step |
| `GET`  | `/run/{run_id}` | Get current run state |

### Example: Execute a Workflow

```bash
curl -X POST http://localhost:8000/execute-workflow \
  -H "Content-Type: application/json" \
  -d '{
    "steps": [
      {"tool": "mock_pm", "input": "Fetch critical issue"},
      {"tool": "slack", "input": "Alert the team"},
      {"tool": "github", "input": "Create follow-up issue"},
      {"tool": "sheets", "input": "Log to escalation sheet"},
      {"tool": "approval", "input": "Approve before escalation"}
    ]
  }'
```

---

*Built with intent by **FlowMind AI** — Team NexaMind | Tic Tech Toe 2026*
