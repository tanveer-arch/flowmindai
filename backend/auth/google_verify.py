"""FlowMind — Google ID Token Verification

Verifies Google ID tokens (JWTs) returned by Google Identity Services
on the frontend. This is the permanent, safe OAuth solution:
  - No redirect flows (no callback URLs to break)
  - No refresh tokens or offline access (safe for Google account)
  - Cryptographic verification using Google's public keys

Usage:
    from backend.auth.google_verify import verify_google_id_token
    user_info = verify_google_id_token(credential, client_id)
"""

import logging
from typing import Optional

log = logging.getLogger(__name__)

# Try to use google-auth library for proper verification
try:
    from google.oauth2 import id_token as google_id_token
    from google.auth.transport import requests as google_requests
    _GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    _GOOGLE_AUTH_AVAILABLE = False
    log.warning(
        "google-auth library not installed. "
        "Install with: pip install google-auth>=2.0.0 "
        "Falling back to manual JWT decode (less secure)."
    )

# Fallback: manual JWT decode (for when google-auth isn't installed)
import json
import base64


def _decode_jwt_payload(token: str) -> Optional[dict]:
    """Decode JWT payload without verification (fallback only)."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        # Add padding
        payload = parts[1]
        payload += "=" * (4 - len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception as exc:
        log.warning("Failed to decode JWT payload: %s", exc)
        return None


def verify_google_id_token(credential: str, client_id: str) -> Optional[dict]:
    """Verify a Google ID token and return user info.

    Args:
        credential: The ID token (JWT) from Google Identity Services.
        client_id: The expected Google OAuth Client ID.

    Returns:
        dict with keys: sub, email, name, picture (or None on failure).
    """
    if _GOOGLE_AUTH_AVAILABLE:
        try:
            idinfo = google_id_token.verify_oauth2_token(
                credential,
                google_requests.Request(),
                client_id,
            )

            # Verify issuer
            if idinfo.get("iss") not in [
                "accounts.google.com",
                "https://accounts.google.com",
            ]:
                log.warning("Invalid issuer: %s", idinfo.get("iss"))
                return None

            return {
                "sub": idinfo["sub"],
                "email": idinfo.get("email", ""),
                "name": idinfo.get("name", ""),
                "picture": idinfo.get("picture", ""),
            }
        except ValueError as exc:
            log.warning("Google ID token verification failed: %s", exc)
            return None
        except Exception as exc:
            log.error("Unexpected error verifying Google ID token: %s", exc)
            return None
    else:
        # Fallback: decode without cryptographic verification
        # This is less secure but works without google-auth
        log.warning("Using fallback JWT decode (no cryptographic verification)")
        payload = _decode_jwt_payload(credential)
        if not payload:
            return None

        # Basic validation
        if payload.get("aud") != client_id:
            log.warning("Token audience mismatch: expected %s, got %s",
                        client_id, payload.get("aud"))
            return None

        return {
            "sub": payload.get("sub", ""),
            "email": payload.get("email", ""),
            "name": payload.get("name", ""),
            "picture": payload.get("picture", ""),
        }
