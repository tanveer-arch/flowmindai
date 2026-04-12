"""FastAPI dependencies for user authentication.

``get_current_user``   — raises 401 if not authenticated
``get_optional_user``  — returns None if not authenticated (for backward-compatible routes)
"""

from fastapi import Request, HTTPException
from typing import Optional

from backend.auth.session_manager import validate_session, SESSION_COOKIE_NAME


def get_current_user(request: Request) -> dict:
    """Dependency: require an authenticated user.

    Reads the session cookie, validates it, and returns a user-info dict.
    Raises 401 if the session is missing or invalid.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = validate_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return {
        "user_id": session["user_id"],
        "email": session["email"],
        "name": session["name"],
        "picture_url": session.get("picture_url", ""),
        "google_sub": session.get("google_sub", ""),
    }


def get_optional_user(request: Request) -> Optional[dict]:
    """Dependency: return authenticated user if present, else None.

    This is used on existing endpoints to add user context WITHOUT
    breaking unauthenticated access.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    session = validate_session(token)
    if not session:
        return None
    return {
        "user_id": session["user_id"],
        "email": session["email"],
        "name": session["name"],
        "picture_url": session.get("picture_url", ""),
        "google_sub": session.get("google_sub", ""),
    }
