"""Security utilities for internal endpoints."""

from __future__ import annotations

from typing import Tuple

from flask import current_app, request

try:
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token
except Exception:  # pragma: no cover
    google_requests = None
    id_token = None



def verify_internal_request() -> Tuple[bool, str]:
    """Validate internal endpoint caller.

    In development mode, this can be bypassed via ALLOW_INSECURE_INTERNAL.
    """
    if current_app.config.get("ALLOW_INSECURE_INTERNAL", False):
        return True, "insecure-dev-allowed"

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return False, "Missing bearer token"

    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return False, "Missing bearer token"

    if id_token is None or google_requests is None:
        return False, "google-auth libraries unavailable"

    audience = current_app.config.get("INTERNAL_TASK_AUDIENCE") or current_app.config.get("TASK_HANDLER_URL")
    if not audience:
        return False, "No INTERNAL_TASK_AUDIENCE configured"

    try:
        id_token.verify_oauth2_token(token, google_requests.Request(), audience=audience)
    except Exception as exc:  # pragma: no cover
        return False, f"Invalid token: {exc}"

    return True, "ok"
