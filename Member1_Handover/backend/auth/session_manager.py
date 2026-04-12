"""Session token manager — creates, validates, and invalidates sessions.

Tokens are secure random strings stored in the ``sessions`` DB table
and delivered to the browser as HTTP-only cookies.
"""

import secrets

from backend.db.repositories import (
    create_session,
    get_session,
    invalidate_session,
    invalidate_user_sessions,
)

SESSION_COOKIE_NAME = "flowmind_session"
SESSION_EXPIRY_HOURS = 24


def create_user_session(user_id: int) -> str:
    """Create a new session for the given user and return the token."""
    token = secrets.token_urlsafe(48)
    create_session(user_id, token, expires_hours=SESSION_EXPIRY_HOURS)
    return token


def validate_session(token: str) -> dict | None:
    """Validate a session token and return session+user data, or None."""
    if not token:
        return None
    return get_session(token)


def logout_session(token: str):
    """Invalidate a single session."""
    if token:
        invalidate_session(token)


def logout_all(user_id: int):
    """Invalidate all sessions for a user."""
    invalidate_user_sessions(user_id)
