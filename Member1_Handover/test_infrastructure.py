"""Infrastructure tests for Member 1: System Backbone.

Tests DB schema, user CRUD, sessions, workflow persistence,
logging service, and rollback service — all offline (no server needed).
"""

import os
import sys
import sqlite3
import json

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Use a test-specific DB to avoid polluting production data
import backend.db.connection as db_conn
TEST_DB = os.path.join(PROJECT_ROOT, "flowmind_test.db")
db_conn.DB_PATH = TEST_DB

# Clean up any previous test DB
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

from backend.db.schema import init_db
from backend.db.repositories import (
    upsert_user, get_user_by_id, get_user_by_google_sub,
    create_session, get_session, invalidate_session,
    save_workflow_template, get_user_workflows,
    save_workflow_run, update_run_status_db, get_user_runs, get_run_details,
    save_workflow_step, update_step_status_db,
    insert_log, get_user_logs,
    save_rollback_action, get_rollback_actions_for_run, update_rollback_status,
)
from backend.services.logging_service import log_event
from backend.services.rollback_service import register_rollback, execute_rollback

passed = 0
failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name}")
        failed += 1


# ──────────────────────────────────────────────────────────────
# TEST 1: Schema Initialization
# ──────────────────────────────────────────────────────────────
print("=" * 60)
print("TEST 1: Database schema initialization")
print("=" * 60)

init_db()
check("DB file created", os.path.exists(TEST_DB))

conn = sqlite3.connect(TEST_DB)
tables = [r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
).fetchall()]
conn.close()

check("users table exists", "users" in tables)
check("sessions table exists", "sessions" in tables)
check("workflow_templates table exists", "workflow_templates" in tables)
check("workflow_runs table exists", "workflow_runs" in tables)
check("workflow_steps table exists", "workflow_steps" in tables)
check("execution_logs table exists", "execution_logs" in tables)
check("rollback_actions table exists", "rollback_actions" in tables)

# Calling init_db again should be safe
init_db()
check("Double init_db is safe (idempotent)", True)


# ──────────────────────────────────────────────────────────────
# TEST 2: User CRUD
# ──────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("TEST 2: User CRUD")
print("=" * 60)

user = upsert_user("google-123", "test@example.com", "Test User", "https://example.com/pic.jpg")
check("User created", user is not None)
check("User has id", user.get("id") is not None)
check("User email matches", user.get("email") == "test@example.com")
check("User name matches", user.get("name") == "Test User")
check("User picture matches", user.get("picture_url") == "https://example.com/pic.jpg")
check("User provider is google", user.get("provider") == "google")
check("User is_active is 1", user.get("is_active") == 1)

user_id = user["id"]

# Upsert same user again (update last_login)
user2 = upsert_user("google-123", "test@example.com", "Test User Updated", "")
check("Upsert updates name", user2.get("name") == "Test User Updated")
check("Upsert does not create duplicate", user2.get("id") == user_id)

# Fetch by ID and by google_sub
by_id = get_user_by_id(user_id)
check("Get user by id works", by_id is not None and by_id["email"] == "test@example.com")
by_sub = get_user_by_google_sub("google-123")
check("Get user by google_sub works", by_sub is not None and by_sub["id"] == user_id)


# ──────────────────────────────────────────────────────────────
# TEST 3: Sessions
# ──────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("TEST 3: Session management")
print("=" * 60)

session = create_session(user_id, "test-token-abc", expires_hours=24)
check("Session created", session is not None)
check("Session has token", session.get("session_token") == "test-token-abc")
check("Session is_active", session.get("is_active") == 1)

fetched = get_session("test-token-abc")
check("Get session works", fetched is not None)
check("Session includes user email", fetched.get("email") == "test@example.com")

# Invalidate
invalidate_session("test-token-abc")
gone = get_session("test-token-abc")
check("Session invalidated", gone is None)


# ──────────────────────────────────────────────────────────────
# TEST 4: Workflow Templates
# ──────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("TEST 4: Workflow templates")
print("=" * 60)

tmpl_id = save_workflow_template(
    user_id=user_id,
    title="Bug Escalation",
    original_prompt="When a bug is reported, escalate",
    generated_plan={"steps": [{"tool": "slack", "input": "notify"}]},
)
check("Template created", tmpl_id is not None and tmpl_id > 0)

templates = get_user_workflows(user_id)
check("Get user workflows returns 1", len(templates) == 1)
check("Template title matches", templates[0]["title"] == "Bug Escalation")


# ──────────────────────────────────────────────────────────────
# TEST 5: Workflow Runs & Steps
# ──────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("TEST 5: Workflow runs & steps")
print("=" * 60)

db_run_id = save_workflow_run(
    user_id=user_id,
    runtime_run_id="abc12345",
    input_prompt="Bug escalation prompt",
    workflow_template_id=tmpl_id,
)
check("Run created", db_run_id is not None and db_run_id > 0)

step1_id = save_workflow_step(db_run_id, 1, "1", "mock_pm", "get_issue", {"priority": "critical"})
step2_id = save_workflow_step(db_run_id, 2, "2", "slack", "send_message", {"channel": "#alerts"})
check("Step 1 created", step1_id > 0)
check("Step 2 created", step2_id > 0)

update_step_status_db(db_run_id, "1", "success", {"success": True, "message": "ok"})
update_step_status_db(db_run_id, "2", "success", {"success": True, "message": "sent"})
update_run_status_db(db_run_id, "completed")

runs = get_user_runs(user_id)
check("Get user runs returns 1", len(runs) == 1)
check("Run status is completed", runs[0]["run_status"] == "completed")

details = get_run_details(db_run_id)
check("Run details has steps", len(details.get("steps", [])) == 2)
check("Step 1 status is success", details["steps"][0]["status"] == "success")


# ──────────────────────────────────────────────────────────────
# TEST 6: Execution Logs
# ──────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("TEST 6: Execution logs")
print("=" * 60)

insert_log(user_id=user_id, log_level="INFO", event_type="test_event",
           message="Test log entry")
log_event("workflow_created", "Test workflow created", user_id=user_id)

logs = get_user_logs(user_id)
check("Logs inserted", len(logs) >= 2)
check("First log has event_type", logs[0].get("event_type") in ("test_event", "workflow_created"))


# ──────────────────────────────────────────────────────────────
# TEST 7: Rollback Actions
# ──────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("TEST 7: Rollback infrastructure")
print("=" * 60)

rb_id = save_rollback_action(
    db_run_id=db_run_id,
    db_step_id=step2_id,
    tool_name="slack",
    rollback_action_type="delete_message",
    rollback_payload={"channel": "#alerts", "ts": "123456"},
)
check("Rollback action created", rb_id > 0)

actions = get_rollback_actions_for_run(db_run_id)
check("Rollback actions fetched", len(actions) == 1)
check("Rollback action is pending", actions[0]["status"] == "pending")

# Execute rollback
results = execute_rollback(db_run_id, user_id=user_id)
check("Rollback executed", len(results) == 1)
check("Rollback result is completed", results[0]["status"] == "completed")

# Verify status updated
actions_after = get_rollback_actions_for_run(db_run_id)
check("Rollback status updated to completed", actions_after[0]["status"] == "completed")


# ──────────────────────────────────────────────────────────────
# TEST 8: register_rollback integration
# ──────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("TEST 8: register_rollback from service layer")
print("=" * 60)

# Create a new run for this test
db_run_id_2 = save_workflow_run(user_id=user_id, runtime_run_id="run-rb-test",
                                 input_prompt="Rollback test")
step_gh_id = save_workflow_step(db_run_id_2, 1, "1", "github", "create_issue", {})

github_result = {
    "success": True,
    "message": "GitHub issue created",
    "data": {"issue_id": "GH-201", "title": "Test", "url": "https://github.com/test"},
}
register_rollback(db_run_id_2, step_gh_id, "github", github_result, user_id=user_id)

gh_actions = get_rollback_actions_for_run(db_run_id_2)
check("GitHub rollback registered", len(gh_actions) == 1)
check("Rollback type is close_issue", gh_actions[0]["rollback_action_type"] == "close_issue")

payload = json.loads(gh_actions[0]["rollback_payload_json"])
check("Rollback payload has issue_id", payload.get("issue_id") == "GH-201")


# ──────────────────────────────────────────────────────────────
# TEST 9: Full persistence service integration
# ──────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("TEST 9: Persistence service integration")
print("=" * 60)

from backend.services.persistence_service import persist_workflow

mock_run = {
    "run_id": "persist-test",
    "status": "completed",
    "steps": [
        {"step_id": "1", "tool": "mock_pm", "action": "get_issue",
         "params": {"raw_input": ""}, "status": "success",
         "result": {"success": True, "message": "ok"}},
        {"step_id": "2", "tool": "slack", "action": "send_message",
         "params": {"raw_input": ""}, "status": "success",
         "result": {"success": True, "message": "sent",
                    "data": {"channel": "#alerts", "ts": "99999"}}},
    ],
}

persist_id = persist_workflow(
    user_id=user_id,
    prompt="Persistence integration test",
    generated_steps=[{"tool": "mock_pm", "input": "fetch"}, {"tool": "slack", "input": "notify"}],
    run=mock_run,
)

check("persist_workflow returns db_run_id", persist_id is not None and persist_id > 0)

detail = get_run_details(persist_id)
check("Persisted run has 2 steps", len(detail.get("steps", [])) == 2)
check("Persisted run status is completed", detail["run_status"] == "completed")

# Unauthenticated persist should return None (not crash)
none_result = persist_workflow(user_id=None, prompt="no user", generated_steps=[], run={})
check("persist_workflow with None user_id returns None", none_result is None)


# ──────────────────────────────────────────────────────────────
# Cleanup
# ──────────────────────────────────────────────────────────────
print()
print("=" * 60)
total = passed + failed
print(f"RESULTS: {passed}/{total} passed, {failed} failed")
if failed == 0:
    print("ALL INFRASTRUCTURE TESTS PASSED")
else:
    print(f"WARNING: {failed} test(s) FAILED")
print("=" * 60)

# Clean up test database
try:
    os.remove(TEST_DB)
    wal = TEST_DB + "-wal"
    shm = TEST_DB + "-shm"
    if os.path.exists(wal):
        os.remove(wal)
    if os.path.exists(shm):
        os.remove(shm)
except Exception:
    pass
