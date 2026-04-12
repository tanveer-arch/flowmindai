"""Database schema initialization for FlowMind.

Calling ``init_db()`` is safe and idempotent — tables are created only
if they do not already exist.
"""

from backend.db.connection import get_db

_SCHEMA_SQL = """
-- 1. users
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    google_sub      TEXT UNIQUE NOT NULL,
    email           TEXT NOT NULL,
    name            TEXT NOT NULL DEFAULT '',
    picture_url     TEXT DEFAULT '',
    provider        TEXT NOT NULL DEFAULT 'google',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active       INTEGER DEFAULT 1
);

-- 2. sessions
CREATE TABLE IF NOT EXISTS sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    session_token   TEXT UNIQUE NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at      TIMESTAMP NOT NULL,
    is_active       INTEGER DEFAULT 1
);

-- 3. workflow_templates (saved workflow definitions / prompts)
CREATE TABLE IF NOT EXISTS workflow_templates (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    title               TEXT NOT NULL DEFAULT '',
    original_prompt     TEXT NOT NULL DEFAULT '',
    generated_plan_json TEXT DEFAULT '{}',
    edited_plan_json    TEXT DEFAULT '{}',
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. workflow_runs (execution instances)
CREATE TABLE IF NOT EXISTS workflow_runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER REFERENCES users(id),
    workflow_template_id INTEGER REFERENCES workflow_templates(id),
    runtime_run_id      TEXT NOT NULL DEFAULT '',
    input_prompt        TEXT NOT NULL DEFAULT '',
    run_status          TEXT NOT NULL DEFAULT 'running',
    started_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at         TIMESTAMP,
    summary_json        TEXT DEFAULT '{}'
);

-- 5. workflow_steps
CREATE TABLE IF NOT EXISTS workflow_steps (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              INTEGER NOT NULL REFERENCES workflow_runs(id),
    step_order          INTEGER NOT NULL,
    runtime_step_id     TEXT NOT NULL DEFAULT '',
    tool_name           TEXT NOT NULL DEFAULT '',
    action_name         TEXT NOT NULL DEFAULT '',
    input_data          TEXT DEFAULT '{}',
    output_data         TEXT DEFAULT '{}',
    status              TEXT NOT NULL DEFAULT 'pending',
    started_at          TIMESTAMP,
    finished_at         TIMESTAMP,
    rollback_supported  INTEGER DEFAULT 0,
    rollback_status     TEXT DEFAULT 'none'
);

-- 6. execution_logs (audit trail)
CREATE TABLE IF NOT EXISTS execution_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER REFERENCES users(id),
    run_id          INTEGER REFERENCES workflow_runs(id),
    step_id         INTEGER REFERENCES workflow_steps(id),
    log_level       TEXT NOT NULL DEFAULT 'INFO',
    event_type      TEXT NOT NULL DEFAULT '',
    message         TEXT NOT NULL DEFAULT '',
    metadata_json   TEXT DEFAULT '{}',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. rollback_actions (compensation metadata)
CREATE TABLE IF NOT EXISTS rollback_actions (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                  INTEGER NOT NULL REFERENCES workflow_runs(id),
    step_id                 INTEGER NOT NULL REFERENCES workflow_steps(id),
    tool_name               TEXT NOT NULL DEFAULT '',
    rollback_action_type    TEXT NOT NULL DEFAULT '',
    rollback_payload_json   TEXT DEFAULT '{}',
    status                  TEXT NOT NULL DEFAULT 'pending',
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    executed_at             TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_sessions_token    ON sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_runs_user         ON workflow_runs(user_id);
CREATE INDEX IF NOT EXISTS idx_steps_run         ON workflow_steps(run_id);
CREATE INDEX IF NOT EXISTS idx_logs_user         ON execution_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_logs_run          ON execution_logs(run_id);
CREATE INDEX IF NOT EXISTS idx_rollback_run      ON rollback_actions(run_id);
"""


def init_db():
    """Create all tables if they do not exist. Safe to call multiple times."""
    with get_db() as conn:
        conn.executescript(_SCHEMA_SQL)
    print("[FlowMind] Database schema initialized.")
