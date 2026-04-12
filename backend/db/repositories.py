"""Repository / CRUD helpers for all FlowMind database tables.

Every function opens its own connection via ``get_db()`` so callers
do not need to manage connections.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.db.connection import get_db


# ──────────────────────────────────────────────────────────────
# Users
# ──────────────────────────────────────────────────────────────

def upsert_user(google_sub: str, email: str, name: str = "",
                picture_url: str = "", provider: str = "google") -> dict:
    """Insert a new user or update last_login_at for an existing one.

    Returns the user row as a dict.
    """
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO users (google_sub, email, name, picture_url, provider, last_login_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(google_sub) DO UPDATE SET
                   name = excluded.name,
                   email = excluded.email,
                   picture_url = excluded.picture_url,
                   last_login_at = excluded.last_login_at""",
            (google_sub, email, name, picture_url, provider, now),
        )
        row = conn.execute("SELECT * FROM users WHERE google_sub = ?", (google_sub,)).fetchone()
    return dict(row) if row else {}


def get_user_by_id(user_id: int) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def get_user_by_google_sub(google_sub: str) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE google_sub = ?", (google_sub,)).fetchone()
    return dict(row) if row else None


# ──────────────────────────────────────────────────────────────
# Sessions
# ──────────────────────────────────────────────────────────────

def create_session(user_id: int, session_token: str,
                   expires_hours: int = 24) -> dict:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=expires_hours)
    with get_db() as conn:
        conn.execute(
            """INSERT INTO sessions (user_id, session_token, created_at, expires_at, is_active)
               VALUES (?, ?, ?, ?, 1)""",
            (user_id, session_token, now.isoformat(), expires.isoformat()),
        )
        row = conn.execute("SELECT * FROM sessions WHERE session_token = ?",
                           (session_token,)).fetchone()
    return dict(row) if row else {}


def get_session(session_token: str) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute(
            """SELECT s.*, u.email, u.name, u.picture_url, u.google_sub
               FROM sessions s JOIN users u ON s.user_id = u.id
               WHERE s.session_token = ? AND s.is_active = 1""",
            (session_token,),
        ).fetchone()
    if not row:
        return None
    session = dict(row)
    # Check expiry
    expires = datetime.fromisoformat(session["expires_at"])
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires:
        invalidate_session(session_token)
        return None
    return session


def invalidate_session(session_token: str):
    with get_db() as conn:
        conn.execute("UPDATE sessions SET is_active = 0 WHERE session_token = ?",
                     (session_token,))


def invalidate_user_sessions(user_id: int):
    with get_db() as conn:
        conn.execute("UPDATE sessions SET is_active = 0 WHERE user_id = ?",
                     (user_id,))


# ──────────────────────────────────────────────────────────────
# Workflow Templates
# ──────────────────────────────────────────────────────────────

def save_workflow_template(user_id: int, title: str, original_prompt: str,
                           generated_plan: dict, edited_plan: dict | None = None) -> int:
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO workflow_templates
               (user_id, title, original_prompt, generated_plan_json, edited_plan_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, title, original_prompt,
             json.dumps(generated_plan), json.dumps(edited_plan or {}),
             now, now),
        )
        return cur.lastrowid


def get_user_workflows(user_id: int, limit: int = 50) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM workflow_templates WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


# ──────────────────────────────────────────────────────────────
# Workflow Runs
# ──────────────────────────────────────────────────────────────

def save_workflow_run(user_id: int | None, runtime_run_id: str,
                      input_prompt: str,
                      workflow_template_id: int | None = None) -> int:
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO workflow_runs
               (user_id, workflow_template_id, runtime_run_id, input_prompt, run_status, started_at)
               VALUES (?, ?, ?, ?, 'running', ?)""",
            (user_id, workflow_template_id, runtime_run_id, input_prompt, now),
        )
        return cur.lastrowid


def update_run_status_db(db_run_id: int, status: str,
                         summary: dict | None = None):
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            """UPDATE workflow_runs
               SET run_status = ?, finished_at = ?, summary_json = ?
               WHERE id = ?""",
            (status, now if status in ("completed", "failed") else None,
             json.dumps(summary or {}), db_run_id),
        )


def get_run_by_runtime_id(runtime_run_id: str) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM workflow_runs WHERE runtime_run_id = ?",
            (runtime_run_id,),
        ).fetchone()
    return dict(row) if row else None


def get_user_runs(user_id: int, limit: int = 50) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM workflow_runs WHERE user_id = ? ORDER BY started_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_run_details(db_run_id: int) -> Optional[dict]:
    with get_db() as conn:
        run_row = conn.execute("SELECT * FROM workflow_runs WHERE id = ?",
                               (db_run_id,)).fetchone()
        if not run_row:
            return None
        run = dict(run_row)
        steps = conn.execute(
            "SELECT * FROM workflow_steps WHERE run_id = ? ORDER BY step_order",
            (db_run_id,),
        ).fetchall()
        run["steps"] = [dict(s) for s in steps]
    return run


# ──────────────────────────────────────────────────────────────
# Workflow Steps
# ──────────────────────────────────────────────────────────────

def save_workflow_step(db_run_id: int, step_order: int,
                       runtime_step_id: str, tool_name: str,
                       action_name: str, input_data: dict) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO workflow_steps
               (run_id, step_order, runtime_step_id, tool_name, action_name, input_data, status)
               VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
            (db_run_id, step_order, runtime_step_id, tool_name,
             action_name, json.dumps(input_data)),
        )
        return cur.lastrowid


def update_step_status_db(db_run_id: int, runtime_step_id: str,
                          status: str, output_data: dict | None = None):
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            """UPDATE workflow_steps
               SET status = ?, output_data = ?,
                   started_at = COALESCE(started_at, ?),
                   finished_at = CASE WHEN ? IN ('success','failed') THEN ? ELSE finished_at END
               WHERE run_id = ? AND runtime_step_id = ?""",
            (status, json.dumps(output_data or {}), now,
             status, now, db_run_id, runtime_step_id),
        )


# ──────────────────────────────────────────────────────────────
# Execution Logs
# ──────────────────────────────────────────────────────────────

def insert_log(user_id: int | None = None, run_id: int | None = None,
               step_id: int | None = None, log_level: str = "INFO",
               event_type: str = "", message: str = "",
               metadata: dict | None = None):
    with get_db() as conn:
        conn.execute(
            """INSERT INTO execution_logs
               (user_id, run_id, step_id, log_level, event_type, message, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, run_id, step_id, log_level, event_type,
             message, json.dumps(metadata or {})),
        )


def get_user_logs(user_id: int, limit: int = 100) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM execution_logs WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


# ──────────────────────────────────────────────────────────────
# Rollback Actions
# ──────────────────────────────────────────────────────────────

def save_rollback_action(db_run_id: int, db_step_id: int,
                         tool_name: str, rollback_action_type: str,
                         rollback_payload: dict) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO rollback_actions
               (run_id, step_id, tool_name, rollback_action_type, rollback_payload_json, status)
               VALUES (?, ?, ?, ?, ?, 'pending')""",
            (db_run_id, db_step_id, tool_name, rollback_action_type,
             json.dumps(rollback_payload)),
        )
        return cur.lastrowid


def get_rollback_actions_for_run(db_run_id: int) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM rollback_actions
               WHERE run_id = ? ORDER BY id DESC""",
            (db_run_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def update_rollback_status(rollback_id: int, status: str):
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            "UPDATE rollback_actions SET status = ?, executed_at = ? WHERE id = ?",
            (status, now, rollback_id),
        )
