"""
FlowMind AI -- Agent Runner
Bridges the LLM Agent Brain (agent.py) with the Backend Executor.

Flow: User Input --> agent.py --> JSON steps --> normalize --> execute_run --> results
"""

import sys
import os
import json

# Ensure project root is on sys.path so both `agent` and `backend.*` resolve.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent import generate_steps
from backend.runtime.normalize import normalize_steps
from backend.runtime.store import create_run
from backend.runtime.executor import execute_run


# ============================================================
# TOOL NAME MAPPING
# ============================================================
# Agent outputs:          "create_github_issue", "send_slack_message", "update_google_sheet"
# Backend expects:        "github",              "slack",              "sheets"
# This map bridges them.

AGENT_TO_BACKEND_TOOL = {
    "create_github_issue":  "github",
    "send_slack_message":   "slack",
    "update_google_sheet":  "sheets",
}


def translate_steps(agent_output: dict) -> dict:
    """Convert agent tool names to backend-compatible tool names.

    Input:  {"steps": [{"tool": "create_github_issue", "input": "..."}]}
    Output: {"steps": [{"tool": "github", "input": "..."}]}
    """
    translated = []
    for step in agent_output.get("steps", []):
        agent_tool = step.get("tool", "")
        backend_tool = AGENT_TO_BACKEND_TOOL.get(agent_tool, agent_tool)
        translated.append({
            "tool": backend_tool,
            "input": step.get("input", "")
        })
    return {"steps": translated}


# ============================================================
# MAIN RUNNER
# ============================================================

def run_workflow(user_input: str) -> dict:
    """Full pipeline: user input -> LLM -> steps -> execute -> results."""

    # Step 1: LLM generates steps
    print("\n" + "=" * 60)
    print("  [1/4] LLM AGENT - Generating workflow steps...")
    print("=" * 60)

    agent_output = generate_steps(user_input)

    if not agent_output.get("steps"):
        print("  No steps generated. Try a different input.")
        return {"status": "empty", "steps": []}

    print(f"  Generated {len(agent_output['steps'])} step(s):")
    for i, step in enumerate(agent_output["steps"], 1):
        print(f"    {i}. {step['tool']}({step['input']})")

    # Step 2: Translate tool names (agent -> backend)
    print("\n" + "=" * 60)
    print("  [2/4] TRANSLATING - Mapping tools to backend connectors...")
    print("=" * 60)

    backend_input = translate_steps(agent_output)

    for i, step in enumerate(backend_input["steps"], 1):
        agent_name = agent_output["steps"][i-1]["tool"]
        backend_name = step["tool"]
        print(f"    {i}. {agent_name} --> {backend_name}")

    # Step 3: Normalize into internal task format
    print("\n" + "=" * 60)
    print("  [3/4] NORMALIZING - Building execution plan...")
    print("=" * 60)

    tasks = normalize_steps(backend_input)

    for task in tasks:
        print(f"    Step {task['step_id']}: tool={task['tool']}, action={task['action']}, status={task['status']}")

    # Step 4: Execute via backend runtime
    print("\n" + "=" * 60)
    print("  [4/4] EXECUTING - Running workflow...")
    print("=" * 60)

    run = create_run(tasks)
    print(f"  Run ID: {run['run_id']}")
    print()

    execute_run(run)

    # Print results
    print("\n" + "=" * 60)
    print("  RESULTS")
    print("=" * 60)

    for step in run["steps"]:
        status_icon = "[OK]" if step["status"] == "success" else "[FAIL]" if step["status"] == "failed" else "[??]"
        result_msg = step.get("result", {}).get("message", "No result") if step.get("result") else "No result"
        print(f"  {status_icon} Step {step['step_id']}: {step['tool']}.{step['action']} -- {result_msg}")

    print(f"\n  Overall: {run['status'].upper()}")
    print("=" * 60)

    return run


# ============================================================
# INTERACTIVE CLI
# ============================================================

def main():
    print("\n" + "=" * 60)
    print("  FlowMind AI -- Full Pipeline Runner")
    print("  LLM Agent + Backend Executor")
    print("  Type a workflow. Type 'quit' to exit.")
    print("=" * 60)

    while True:
        user_input = input("\n>>> ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            print("Done.")
            break
        if not user_input:
            continue

        run_workflow(user_input)


def run_demo():
    """Run a single hardcoded demo for testing."""
    demo_input = "Create a GitHub issue for login bug, notify the team on Slack, and log it in the tracking sheet"
    print(f"\n  DEMO INPUT: \"{demo_input}\"")
    run_workflow(demo_input)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        run_demo()
    else:
        main()
