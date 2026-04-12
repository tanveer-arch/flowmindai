"""Google OAuth 2.0 helpers for FlowMind backend authentication.

Uses the standard Authorization Code flow:
  1. ``get_authorization_url()``  — build Google consent redirect
  2. ``exchange_code()``          — swap auth code for ID token payload
"""

import os
import requests as http_requests
from urllib.parse import urlencode

from dotenv import load_dotenv
from pathlib import Path

# Load .env from the project root (FlowMind/)
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ENV_PATH)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI",
                                "http://127.0.0.1:8000/auth/callback")

_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
_USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"


def get_authorization_url(state: str = "") -> str:
    """Return the Google OAuth consent URL."""
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    if state:
        params["state"] = state
    return f"{_AUTH_ENDPOINT}?{urlencode(params)}"


def exchange_code(code: str) -> dict:
    """Exchange an authorization code for tokens and return user info.

    Returns a dict with keys: ``sub``, ``email``, ``name``, ``picture``.
    Raises ``ValueError`` on failure.
    """
    # 1. Exchange code for tokens
    token_resp = http_requests.post(_TOKEN_ENDPOINT, data={
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }, timeout=10)

    if token_resp.status_code != 200:
        raise ValueError(f"Token exchange failed: {token_resp.text}")

    tokens = token_resp.json()
    access_token = tokens.get("access_token", "")

    # 2. Fetch user info
    userinfo_resp = http_requests.get(_USERINFO_ENDPOINT, headers={
        "Authorization": f"Bearer {access_token}",
    }, timeout=10)

    if userinfo_resp.status_code != 200:
        raise ValueError(f"Userinfo request failed: {userinfo_resp.text}")

    info = userinfo_resp.json()
    return {
        "sub": info.get("sub", ""),
        "email": info.get("email", ""),
        "name": info.get("name", ""),
        "picture": info.get("picture", ""),
    }
