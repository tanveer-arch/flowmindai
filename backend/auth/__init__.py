"""FlowMind Auth Package
Exposes:
  - router: FastAPI router with Google OAuth endpoints (standalone in-memory sessions)
  - get_optional_user: Extract user from Authorization header
"""

from backend.auth.standalone import router, get_optional_user, get_user_from_token

__all__ = ["router", "get_optional_user", "get_user_from_token"]
