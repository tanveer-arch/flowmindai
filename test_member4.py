"""FlowMind integration smoke test — Member 4"""
import sys
sys.path.insert(0, ".")

from backend.runtime.normalize import normalize_steps, translate_agent_steps
from backend.runtime import store
from backend.runtime.executor import execute_run

# ---------- TEST 1: normalize_steps ----------
print("=== TEST 1: normalize_steps with params schema ===")
raw_steps = [
    {"tool": "create_jira_ticket",  "params": {"summary": "Bug found", "description": "Login page crash", "priority": "High"}},
    {"tool": "create_github_issue", "params": {"title": "Bug: Login crash (Jira: JRA-?)", "body": "Related to JRA-?"}},
    {"tool": "update_google_sheet", "params": {"sheet_name": "Bug Log", "row_data": {"jira_id": "JRA-?", "status": "open"}}},
    {"tool": "request_approval",    "params": {"reason": "About to notify clients"}},
    {"tool": "request_user_input",  "params": {"question": "What should the email say?"}},
    {"tool": "send_email",          "params": {"to": "client@test.com", "subject": "Bug update", "body": "See Jira."}},
]
steps = normalize_steps(raw_steps)
for s in steps:
    print("  %s | tool=%s | action=%s | requires_approval=%s" % (s["step_id"], s["tool"], s["action"], s["requires_approval"]))
assert len(steps) == 6, "Expected 6 steps"
assert steps[0]["tool"] == "jira"
assert steps[0]["action"] == "create_ticket"
assert steps[3]["tool"] == "approval"
assert steps[3]["requires_approval"] is True
assert steps[4]["tool"] == "request_user_input"
assert steps[5]["tool"] == "email"
print("  PASS")

# ---------- TEST 2: translate_agent_steps ----------
print()
print("=== TEST 2: translate_agent_steps ===")
agent_out = {"steps": [
    {"tool": "create_jira_ticket", "params": {"summary": "Test"}},
    {"tool": "send_email",         "params": {"to": "a@b.com", "subject": "Hi", "body": "Hello"}},
]}
translated = translate_agent_steps(agent_out)
assert translated["steps"][0]["tool"] == "jira"
assert translated["steps"][1]["tool"] == "email"
print("  jira, email  PASS")

# ---------- TEST 3: full executor run ----------
print()
print("=== TEST 3: full executor run (jira + github + sheets) ===")
steps = normalize_steps([
    {"tool": "create_jira_ticket",  "params": {"summary": "Test bug", "description": "desc", "priority": "High"}},
    {"tool": "create_github_issue", "params": {"title": "Test GH issue", "body": "linked to JRA-?"}},
    {"tool": "update_google_sheet", "params": {"sheet_name": "Bugs", "row_data": {"entry": "1"}}},
])
run = store.create_run(steps, "test prompt")
execute_run(run)
print("  run status: %s" % run["status"])
for s in run["steps"]:
    res = s.get("result") or {}
    print("  %s %s -> status=%s success=%s" % (s["step_id"], s["tool"], s["status"], res.get("success")))
assert run["status"] == "completed", "Expected completed, got: " + run["status"]
print("  PASS")

# ---------- TEST 4: approval gate ----------
print()
print("=== TEST 4: approval gate pauses execution ===")
steps = normalize_steps([
    {"tool": "create_jira_ticket", "params": {"summary": "Sensitive", "description": "", "priority": "Medium"}},
    {"tool": "request_approval",   "params": {"reason": "Need approval before email"}},
    {"tool": "send_email",         "params": {"to": "boss@co.com", "subject": "Alert", "body": "Doing sensitive thing"}},
])
run2 = store.create_run(steps, "approval test")
execute_run(run2)
print("  run status after first execute: %s" % run2["status"])
assert run2["status"] == "waiting_approval", "Expected waiting_approval"
# Now simulate approval
store.update_step(run2["run_id"], "step_1", "success", {"success": True, "message": "approved", "data": {}})
execute_run(run2, start_from_step="step_2")
print("  run status after approval: %s" % run2["status"])
assert run2["status"] == "completed", "Expected completed after approval"
print("  PASS")

# ---------- TEST 5: user-input gate ----------
print()
print("=== TEST 5: user-input gate pauses execution ===")
steps = normalize_steps([
    {"tool": "request_user_input", "params": {"question": "What email should I send?"}},
    {"tool": "send_email",         "params": {"to": "user@co.com", "subject": "Your request", "body": "TBD"}},
])
run3 = store.create_run(steps, "user input test")
execute_run(run3)
print("  run status after first execute: %s" % run3["status"])
assert run3["status"] == "waiting_user_input", "Expected waiting_user_input"
print("  PASS")

print()
print("ALL 5 FUNCTIONAL TESTS PASSED.")
