"""Tests for the Self-Healing / Adaptive Retry Engine.

These tests run offline (no server needed).  They exercise the recovery
engine directly by monkey-patching the connector ``dispatch`` function.
"""

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.runtime.recovery_engine import (
    classify_error,
    is_retryable,
    is_critical,
    safe_dispatch,
    MAX_RETRIES,
)
from backend.runtime import store
from backend.runtime.executor import execute_run

# ──────────────────────────────────────────────────────────────
# Helper: build a minimal step dict
# ──────────────────────────────────────────────────────────────

def _make_step(tool="slack", action="send_message", step_id="1"):
    return {
        "step_id": step_id,
        "tool": tool,
        "action": action,
        "params": {"raw_input": "test"},
        "requires_approval": False,
        "status": "pending",
        "result": None,
    }


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
# TEST 1 — Failure Classification
# ──────────────────────────────────────────────────────────────
print("=" * 60)
print("TEST 1: Failure classification")
print("=" * 60)

check("timeout -> transient_error",
      classify_error("Connection timed out") == "transient_error")
check("rate limit -> transient_error",
      classify_error("rate limit exceeded") == "transient_error")
check("unsupported action -> input_error",
      classify_error("Unsupported action 'foo' for slack connector") == "input_error")
check("permission denied -> input_error",
      classify_error("Permission denied") == "input_error")
check("random string -> unknown_error",
      classify_error("something weird happened") == "unknown_error")
check("transient is retryable",
      is_retryable("transient_error") is True)
check("input_error is NOT retryable",
      is_retryable("input_error") is False)
check("unknown_error is NOT retryable",
      is_retryable("unknown_error") is False)

# ──────────────────────────────────────────────────────────────
# TEST 2 — Criticality Inference
# ──────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("TEST 2: Criticality inference")
print("=" * 60)

check("slack is non-critical", is_critical("slack") is False)
check("sheets is non-critical", is_critical("sheets") is False)
check("mock_pm is critical", is_critical("mock_pm") is True)
check("github is critical", is_critical("github") is True)
check("unknown tool defaults to critical", is_critical("some_new_tool") is True)

# ──────────────────────────────────────────────────────────────
# TEST 3 — Happy path (no recovery needed)
# ──────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("TEST 3: Happy path — no recovery")
print("=" * 60)

step = _make_step("slack", "send_message")
result = safe_dispatch(step, {"channel": "#test", "text": "hello"})
check("success is True", result["success"] is True)
check("retry_count is 0", result["retry_count"] == 0)
check("fallback_used is False", result["fallback_used"] is False)
check("recovery_status is 'original'", result["recovery_status"] == "original")

# ──────────────────────────────────────────────────────────────
# TEST 4 — Retry scenario (transient failure then success)
# ──────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("TEST 4: Retry — transient error then success")
print("=" * 60)

import backend.connectors.registry as registry

_original_dispatch = registry.dispatch
_call_count = 0


def _mock_dispatch_transient_then_ok(tool, action, params):
    """First call fails with transient error, second call succeeds."""
    global _call_count
    _call_count += 1
    if _call_count == 1:
        return {"success": False, "message": "Connection timed out", "data": {}}
    return {"success": True, "message": "Message sent OK", "data": {"ts": "123"}}


# Monkey-patch
registry.dispatch = _mock_dispatch_transient_then_ok
# Need to also patch the import in recovery_engine module
import backend.runtime.recovery_engine as re_module
re_module.dispatch = _mock_dispatch_transient_then_ok

_call_count = 0
step = _make_step("slack", "send_message")
result = safe_dispatch(step, {"channel": "#test", "text": "hello"})

check("success after retry", result["success"] is True)
check("retry_count is 1", result["retry_count"] == 1)
check("fallback_used is False", result["fallback_used"] is False)
check("recovery_status is 'retried'", result["recovery_status"] == "retried")
check("error_category is 'transient_error'", result["error_category"] == "transient_error")

# Restore
registry.dispatch = _original_dispatch
re_module.dispatch = _original_dispatch

# ──────────────────────────────────────────────────────────────
# TEST 5 — Fallback scenario (non-critical tool, permanent failure)
# ──────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("TEST 5: Fallback — Slack permanent failure")
print("=" * 60)


def _mock_dispatch_permanent_fail(tool, action, params):
    return {"success": False, "message": "Unsupported action 'bad'", "data": {}}


registry.dispatch = _mock_dispatch_permanent_fail
re_module.dispatch = _mock_dispatch_permanent_fail

step = _make_step("slack", "send_message")
result = safe_dispatch(step, {"channel": "#test", "text": "hello"})

check("success via fallback", result["success"] is True)
check("fallback_used is True", result["fallback_used"] is True)
check("recovery_status is 'fallback'", result["recovery_status"] == "fallback")
check("error_category is 'input_error'", result["error_category"] == "input_error")

registry.dispatch = _original_dispatch
re_module.dispatch = _original_dispatch

# ──────────────────────────────────────────────────────────────
# TEST 6 — Critical tool failure stops workflow
# ──────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("TEST 6: Critical failure — mock_pm stops workflow")
print("=" * 60)

registry.dispatch = _mock_dispatch_permanent_fail
re_module.dispatch = _mock_dispatch_permanent_fail

step = _make_step("mock_pm", "get_issue")
result = safe_dispatch(step, {"priority": "critical"})

check("success is False (critical)", result["success"] is False)
check("fallback_used is False", result["fallback_used"] is False)
check("recovery_status is 'failed'", result["recovery_status"] == "failed")

registry.dispatch = _original_dispatch
re_module.dispatch = _original_dispatch

# ──────────────────────────────────────────────────────────────
# TEST 7 — Full workflow with mixed failures via executor
# ──────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("TEST 7: Full workflow — sheets fails, workflow continues")
print("=" * 60)

_sheets_call = 0


def _mock_dispatch_sheets_fail(tool, action, params):
    """Let everything succeed except sheets."""
    global _sheets_call
    if tool == "sheets":
        _sheets_call += 1
        return {"success": False, "message": "Connection timed out to Sheets API", "data": {}}
    return _original_dispatch(tool, action, params)


registry.dispatch = _mock_dispatch_sheets_fail
re_module.dispatch = _mock_dispatch_sheets_fail

tasks = [
    _make_step("mock_pm", "get_issue", "1"),
    _make_step("slack", "send_message", "2"),
    _make_step("sheets", "append_row", "3"),
]
run = store.create_run(tasks)
execute_run(run)

check("run completes despite sheets failure",
      run["status"] == "completed")
check("mock_pm succeeded", run["steps"][0]["status"] == "success")
check("slack succeeded", run["steps"][1]["status"] == "success")
# Sheets should have been recovered (fallback or continued)
sheets_result = run["steps"][2].get("result", {})
check("sheets was recovered (success=True via fallback)",
      run["steps"][2]["status"] == "success")
check("sheets fallback_used or continued",
      sheets_result.get("fallback_used") is True or sheets_result.get("recovery_status") == "continued_after_failure")

registry.dispatch = _original_dispatch
re_module.dispatch = _original_dispatch

# ──────────────────────────────────────────────────────────────
# TEST 8 — Normal happy-path workflow still works end-to-end
# ──────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("TEST 8: Normal workflow — zero recovery needed (regression)")
print("=" * 60)

tasks = [
    _make_step("mock_pm", "get_issue", "1"),
    _make_step("slack", "send_message", "2"),
    _make_step("github", "create_issue", "3"),
    _make_step("sheets", "append_row", "4"),
]
run = store.create_run(tasks)
execute_run(run)

check("run status is completed", run["status"] == "completed")
for s in run["steps"]:
    check(f"step {s['step_id']} ({s['tool']}) succeeded", s["status"] == "success")
    r = s.get("result", {})
    check(f"step {s['step_id']} recovery_status is 'original'",
          r.get("recovery_status") == "original")
    check(f"step {s['step_id']} retry_count is 0", r.get("retry_count") == 0)
    check(f"step {s['step_id']} fallback_used is False", r.get("fallback_used") is False)


# ──────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────
print()
print("=" * 60)
total = passed + failed
print(f"RESULTS: {passed}/{total} passed, {failed} failed")
if failed == 0:
    print("ALL RECOVERY ENGINE TESTS PASSED")
else:
    print(f"WARNING: {failed} test(s) FAILED")
print("=" * 60)
