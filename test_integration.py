"""Quick integration smoke test — run from project root."""
import sys, os
sys.path.insert(0, ".")
os.environ.setdefault("GROQ_API_KEY", "dummy_for_test")

def ok(label):
    print(f"  [OK] {label}")

def fail(label, exc):
    print(f"  [FAIL] {label}: {exc}")
    sys.exit(1)

print("\n=== FlowMind Integration Smoke Test ===\n")

try:
    from backend.runtime.store import create_run, get_run, update_step, log_event, add_log, get_logs, get_all_runs
    ok("store imports")
except Exception as e:
    fail("store imports", e)

try:
    from backend.runtime.normalize import normalize_steps, AGENT_TOOL_REMAP
    ok("normalize imports")
except Exception as e:
    fail("normalize imports", e)

try:
    from backend.connectors.registry import dispatch
    ok("registry imports")
except Exception as e:
    fail("registry imports", e)

try:
    from backend.connectors import jira, github, sheets, email
    ok("connector imports")
except Exception as e:
    fail("connector imports", e)

try:
    from backend.auth import router, get_optional_user
    ok("auth package imports")
except Exception as e:
    fail("auth package imports", e)

try:
    from backend.app import app
    ok("app imports (FastAPI)")
except Exception as e:
    fail("app imports", e)

# Functional test
try:
    steps = normalize_steps([
        {"tool": "create_jira_ticket", "params": {"summary": "Test bug", "description": "Test"}},
        {"tool": "create_github_issue", "params": {"title": "Test issue", "body": "Test"}},
        {"tool": "send_email", "params": {"to": "test@test.com", "subject": "Test", "body": "Hello"}},
    ])
    assert len(steps) == 3, f"Expected 3 steps, got {len(steps)}"
    assert steps[0]["tool"] == "jira", f"Expected jira, got {steps[0]['tool']}"
    assert steps[1]["tool"] == "github"
    assert steps[2]["tool"] == "email"
    ok(f"normalize_steps: {len(steps)} steps, tools={[s['tool'] for s in steps]}")
except Exception as e:
    fail("normalize_steps", e)

try:
    tasks = normalize_steps([{"tool": "create_jira_ticket", "params": {"summary": "Bug #1"}}])
    run = create_run(tasks, "create jira ticket for bug", user_id="test-user")
    rid = run["run_id"]
    assert run["status"] == "pending"
    assert run["user_id"] == "test-user"
    ok(f"create_run: run_id={rid}, status={run['status']}")

    update_step(rid, "step_0", "running")
    log_event(rid, "step_0", "info", "Step started")
    add_log(rid, "step_0", "info", "Alias add_log works")
    logs = get_logs(rid)
    assert len(logs) >= 2, f"Expected >=2 logs, got {len(logs)}"
    ok(f"update_step + log_event + get_logs: {len(logs)} entries")

    runs = get_all_runs()
    assert len(runs) >= 1
    ok(f"get_all_runs: {len(runs)} runs")
except Exception as e:
    fail("store functional test", e)

try:
    result = dispatch("jira", "create_ticket", {"summary": "Mock ticket test"})
    assert result["success"] is True, f"Expected success, got {result}"
    ok(f"dispatch jira: {result['message']}")
except Exception as e:
    fail("dispatch jira", e)

try:
    result = dispatch("github", "create_issue", {"title": "Mock issue", "body": "Test"})
    if not result.get("success"):
        raise RuntimeError(f"Expected success, got {result}")
    ok(f"dispatch github: {result['message']}")
except Exception as e:
    fail("dispatch github", str(e))

try:
    result = dispatch("email", "send_email", {"to": "test@test.com", "subject": "Test", "body": "Hello"})
    assert result["success"] is True
    ok(f"dispatch email: {result['message']}")
except Exception as e:
    fail("dispatch email", e)

print("\n" + "="*40)
print("  ALL TESTS PASSED ✓")
print("="*40 + "\n")
