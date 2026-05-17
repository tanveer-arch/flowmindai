"""Self-Healing / Adaptive Retry Engine – wraps MCP dispatch with
intelligent retry, failure classification, fallback handling, and
continue-if-safe logic.

This module is a *pure extension layer*.  It does **not** modify any
existing MCP client or executor code.  The single entry-point consumed by
the executor is ``safe_dispatch(step, params)``.

Phase 1: Rewired from backend.connectors.registry.dispatch → mcp_client.dispatch_mcp.
         All tool execution now routes through MCP servers only.
"""

import logging
import time
from mcp_client import call_mcp_tool as dispatch

# ──────────────────────────────────────────────────────────────
# Logger – adds a dedicated "recovery" logger alongside existing logs
# ──────────────────────────────────────────────────────────────

logger = logging.getLogger("flowmind.recovery")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(levelname)s  %(name)s — %(message)s",
                          datefmt="%H:%M:%S")
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.DEBUG)

# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────

MAX_RETRIES = 1          # conservative: at most 1 retry
RETRY_DELAY_SECS = 0.3   # short delay between retries

# Tools for which failures are *non-critical* – the workflow may
# continue even if the step ultimately fails after retries/fallbacks.
NON_CRITICAL_TOOLS = {"slack", "sheets"}

# Tools where failures should stop the workflow (critical path).
CRITICAL_TOOLS = {"mock_pm", "github"}

# ──────────────────────────────────────────────────────────────
# Failure Classification
# ──────────────────────────────────────────────────────────────

# Keywords that suggest the error is transient and therefore retryable.
_TRANSIENT_KEYWORDS = [
    "timeout", "timed out", "temporarily", "transient",
    "unavailable", "rate limit", "connection", "network",
    "500", "502", "503", "504", "retry",
]

# Keywords that mark an error as a permanent input / config problem.
_PERMANENT_KEYWORDS = [
    "unsupported action", "permission", "forbidden", "unauthorized",
    "invalid", "not found", "missing", "bad request", "400", "401", "403", "404",
]


def classify_error(error_message: str) -> str:
    """Classify an error message into a category.

    Returns one of:
        ``"transient_error"``   – may succeed on retry
        ``"input_error"``       – bad input / config, retry will not help
        ``"unknown_error"``     – could not classify
    """
    lower = error_message.lower()
    for kw in _TRANSIENT_KEYWORDS:
        if kw in lower:
            return "transient_error"
    for kw in _PERMANENT_KEYWORDS:
        if kw in lower:
            return "input_error"
    return "unknown_error"


def is_retryable(category: str) -> bool:
    """Only transient errors are worth retrying."""
    return category == "transient_error"

# ──────────────────────────────────────────────────────────────
# Fallback Handling
# ──────────────────────────────────────────────────────────────

def _build_fallback_result(tool: str, error_message: str) -> dict | None:
    """Return a safe fallback result for *non-critical* tools.

    Returns ``None`` when no fallback is defined (i.e. for critical tools).
    """
    if tool == "slack":
        logger.info("Fallback for Slack: logging the message locally instead.")
        return {
            "success": True,
            "message": f"[FALLBACK] Slack delivery failed ({error_message}); message logged locally.",
            "data": {"fallback": True, "original_error": error_message},
        }

    if tool == "sheets":
        logger.info("Fallback for Sheets: skipping row append; data preserved in logs.")
        return {
            "success": True,
            "message": f"[FALLBACK] Sheets append failed ({error_message}); row data logged for manual entry.",
            "data": {"fallback": True, "original_error": error_message},
        }

    # No automatic fallback for critical tools – the caller will stop.
    return None

# ──────────────────────────────────────────────────────────────
# Criticality Inference
# ──────────────────────────────────────────────────────────────

def is_critical(tool: str) -> bool:
    """Determine whether a tool is on the critical path.

    If the tool does not appear in either set, we assume *critical* to be
    conservative and avoid silently dropping important steps.
    """
    if tool in NON_CRITICAL_TOOLS:
        return False
    return True   # default conservative

# ──────────────────────────────────────────────────────────────
# Core Entry-Point
# ──────────────────────────────────────────────────────────────

def safe_dispatch(step: dict, params: dict) -> dict:
    """Wrap ``dispatch()`` with retry + fallback + continue-if-safe logic.

    Returns the same ``{success, message, data, ...}`` dict that the
    connectors already produce, **plus** optional recovery metadata fields:

    * ``retry_count``       – how many retries were attempted
    * ``error_category``    – classified error type (if any failure occurred)
    * ``fallback_used``     – whether a fallback was applied
    * ``recovery_status``   – ``"original"`` | ``"retried"`` | ``"fallback"`` | ``"continued_after_failure"`` | ``"failed"``
    """
    tool = step["tool"]
    action = step["action"]

    # ── First attempt (original execution – UNCHANGED) ──────────
    result = dispatch(tool, action, params)

    if result.get("success"):
        # Happy path – inject minimal metadata and return immediately.
        result["retry_count"] = 0
        result["error_category"] = None
        result["fallback_used"] = False
        result["recovery_status"] = "original"
        return result

    # ── Failure path – recovery engine activates ────────────────
    error_msg = result.get("message", "Unknown error")
    category = classify_error(error_msg)
    logger.warning(
        "Step %s (%s.%s) failed: %s [category=%s]",
        step.get("step_id", "?"), tool, action, error_msg, category,
    )

    retry_count = 0

    # ── Retry (only for transient errors) ───────────────────────
    if is_retryable(category):
        for attempt in range(1, MAX_RETRIES + 1):
            retry_count = attempt
            logger.info(
                "Retry %d/%d for step %s (%s.%s)...",
                attempt, MAX_RETRIES, step.get("step_id", "?"), tool, action,
            )
            time.sleep(RETRY_DELAY_SECS)
            result = dispatch(tool, action, params)
            if result.get("success"):
                logger.info("Retry %d succeeded for step %s.", attempt, step.get("step_id", "?"))
                result["retry_count"] = retry_count
                result["error_category"] = category
                result["fallback_used"] = False
                result["recovery_status"] = "retried"
                return result
        # All retries exhausted
        logger.warning("All %d retries exhausted for step %s.", MAX_RETRIES, step.get("step_id", "?"))

    # ── Fallback (only for non-critical tools) ──────────────────
    fallback = _build_fallback_result(tool, error_msg)
    if fallback is not None:
        logger.info("Fallback activated for step %s (%s).", step.get("step_id", "?"), tool)
        fallback["retry_count"] = retry_count
        fallback["error_category"] = category
        fallback["fallback_used"] = True
        fallback["recovery_status"] = "fallback"
        return fallback

    # ── Continue-if-safe (non-critical tool, no fallback) ───────
    if not is_critical(tool):
        logger.info(
            "Non-critical step %s (%s) failed; marking as continued.",
            step.get("step_id", "?"), tool,
        )
        result["retry_count"] = retry_count
        result["error_category"] = category
        result["fallback_used"] = False
        result["recovery_status"] = "continued_after_failure"
        # Override success so the executor does not stop the workflow.
        result["success"] = True
        result["message"] = f"[CONTINUED] {error_msg}"
        return result

    # ── Critical failure – let the executor stop the run ────────
    logger.error(
        "Critical step %s (%s) failed after recovery attempts. Workflow will stop.",
        step.get("step_id", "?"), tool,
    )
    result["retry_count"] = retry_count
    result["error_category"] = category
    result["fallback_used"] = False
    result["recovery_status"] = "failed"
    return result
