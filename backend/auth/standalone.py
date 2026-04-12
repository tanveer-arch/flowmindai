"""FlowMind — Standalone Google OAuth Authentication (Members2&3)
File: backend/auth.py

A lightweight auth module that uses an in-memory session store.
This is INDEPENDENT of the SQLite-backed Member 1 auth system and is
the primary auth path for the integrated project.

Routes:
    GET  /auth/google/login     → Google OAuth redirect
    GET  /auth/google/callback  → Exchange code, create session, redirect
    GET  /auth/me               → Current user (from Bearer token)
    POST /auth/logout           → Destroy session
"""

import os
import secrets
import logging

import requests as http_requests
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])

# ── Config ────────────────────────────────────────────────────────
GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI  = os.getenv(
    "GOOGLE_REDIRECT_URI",
    "http://localhost:8081/auth/google/callback",
)

GOOGLE_AUTH_URL     = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL    = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# ── In-memory session store: token → user info ────────────────────
_sessions: dict[str, dict] = {}


# ── Helper functions ──────────────────────────────────────────────

def get_user_from_token(token: str) -> dict | None:
    """Look up user info from a session token."""
    return _sessions.get(token)


def get_optional_user(request: Request) -> dict | None:
    """Extract user from Authorization header. Returns None if absent/invalid."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    return _sessions.get(token)


# ── Routes ────────────────────────────────────────────────────────

@router.get("/google/login")
def google_login():
    """Redirect user to Google's OAuth consent screen."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="GOOGLE_CLIENT_ID not configured. Add it to .env",
        )

    params = {
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope":         "openid email profile",
        "access_type":   "offline",
        "prompt":        "consent",
    }
    url = GOOGLE_AUTH_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url)


@router.get("/google/callback")
def google_callback(code: str = ""):
    """Handle Google OAuth callback — exchange code for token."""
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    token_resp = http_requests.post(GOOGLE_TOKEN_URL, data={
        "code":          code,
        "client_id":     GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri":  GOOGLE_REDIRECT_URI,
        "grant_type":    "authorization_code",
    }, timeout=15)

    if token_resp.status_code != 200:
        raise HTTPException(
            status_code=400,
            detail=f"Token exchange failed: {token_resp.text[:200]}",
        )

    access_token = token_resp.json().get("access_token")

    profile_resp = http_requests.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if profile_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to fetch user profile")

    profile = profile_resp.json()

    # Create session
    session_token = secrets.token_hex(32)
    user = {
        "user_id": profile.get("id", ""),
        "email":   profile.get("email", ""),
        "name":    profile.get("name", ""),
        "picture": profile.get("picture", ""),
    }
    _sessions[session_token] = user
    log.info("auth: user logged in — %s", user["email"])

    # Redirect frontend with token
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    return RedirectResponse(
        f"{frontend_url}?token={session_token}&name={user['name']}&email={user['email']}"
    )


@router.get("/me")
def get_current_user(request: Request):
    """Return current user info from session token."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = auth_header[7:]
    user = _sessions.get(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return user


@router.post("/logout")
def logout(request: Request):
    """Destroy user session."""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
    _sessions.pop(token, None)
    return {"message": "Logged out"}
