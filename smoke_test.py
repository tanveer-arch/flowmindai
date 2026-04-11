"""Smoke test for FlowMind runtime endpoints."""

import requests
import json

BASE = "http://127.0.0.1:8000"

print("=" * 60)
print("TEST 1: POST /execute-workflow")
print("=" * 60)

payload = {
    "steps": [
        {"tool": "mock_pm", "input": "Fetch the critical issue details"},
        {"tool": "slack", "input": "Send an alert to #alerts about the critical issue"},
        {"tool": "github", "input": "Create a follow-up GitHub issue for the critical issue"},
        {"tool": "sheets", "input": "Append the issue details to the escalation log"},
        {"tool": "approval", "input": "Ask for approval before escalation"},
    ]
}

r = requests.post(f"{BASE}/execute-workflow", json=payload)
run = r.json()
print(json.dumps(run, indent=2))

run_id = run["run_id"]
print(f"\nRun ID: {run_id}")
print(f"Run status: {run['status']}")
for s in run["steps"]:
    print(f"  Step {s['step_id']} ({s['tool']}/{s['action']}): {s['status']}")

assert run["status"] == "waiting_approval", f"Expected waiting_approval, got {run['status']}"
assert run["steps"][4]["status"] == "waiting_approval"
print("\n[PASS] Workflow executed and paused at approval step!")

print()
print("=" * 60)
print("TEST 2: GET /run/{run_id}")
print("=" * 60)

r2 = requests.get(f"{BASE}/run/{run_id}")
run2 = r2.json()
print(f"Status code: {r2.status_code}")
print(f"Run status: {run2['status']}")
assert r2.status_code == 200
assert run2["status"] == "waiting_approval"
print("\n[PASS] Run state retrieved correctly!")

print()
print("=" * 60)
print("TEST 3: POST /approve-step")
print("=" * 60)

r3 = requests.post(f"{BASE}/approve-step", json={"run_id": run_id, "step_id": "5"})
final = r3.json()
print(json.dumps(final, indent=2))

print(f"\nFinal run status: {final['status']}")
for s in final["steps"]:
    print(f"  Step {s['step_id']} ({s['tool']}/{s['action']}): {s['status']}")

assert final["status"] == "completed", f"Expected completed, got {final['status']}"
assert all(s["status"] == "success" for s in final["steps"])
print("\n[PASS] Approval granted, run completed!")

print()
print("=" * 60)
print("ALL SMOKE TESTS PASSED")
print("=" * 60)
