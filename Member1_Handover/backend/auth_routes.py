"""Authentication routes for FlowMind.

Mounted at ``/auth`` on the main FastAPI app.
Provides: login redirect, OAuth callback, current-user, and logout.
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse

from backend.auth.google_auth import get_authorization_url, exchange_code, GOOGLE_CLIENT_ID
from backend.auth.session_manager import (
    create_user_session,
    logout_session,
    SESSION_COOKIE_NAME,
)
from backend.auth.dependencies import get_current_user
from backend.db.repositories import upsert_user
from backend.services.logging_service import log_event

router = APIRouter(prefix="/auth", tags=["auth"])

# Frontend URL to redirect to after login/logout
_FRONTEND_URL = "http://127.0.0.1:5500/"


@router.get("/login")
def login():
    """Redirect the user to Google's OAuth consent page."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env",
        )
    url = get_authorization_url()
    return RedirectResponse(url=url)


@router.get("/callback")
def auth_callback(request: Request, code: str = "", error: str = ""):
    """Handle the OAuth callback from Google."""
    if error:
        raise HTTPException(status_code=400, detail=f"OAuth error: {error}")

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    try:
        user_info = exchange_code(code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Upsert user in DB
    user = upsert_user(
        google_sub=user_info["sub"],
        email=user_info["email"],
        name=user_info["name"],
        picture_url=user_info.get("picture", ""),
    )

    # Create session
    token = create_user_session(user["id"])

    log_event("user_login",
              f"User {user['email']} logged in",
              user_id=user["id"])

    # Redirect to frontend with session cookie
    response = RedirectResponse(url=_FRONTEND_URL)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400,  # 24 hours
        path="/",
    )
    return response


@router.get("/me")
def current_user(user: dict = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return {
        "authenticated": True,
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user["name"],
        "picture_url": user.get("picture_url", ""),
    }


@router.post("/logout")
def logout(request: Request):
    """Invalidate the current session and clear the cookie."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        logout_session(token)

    response = RedirectResponse(url=_FRONTEND_URL, status_code=303)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response
