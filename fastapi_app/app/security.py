from __future__ import annotations

import secrets

from fastapi import HTTPException, Request, status

from app.config import settings


CSRF_SESSION_KEY = "csrf_token"


def get_csrf_token(request: Request) -> str:
    token = request.session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        request.session[CSRF_SESSION_KEY] = token
    return token


def require_safe_browser_request(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin not in settings.allowed_origins:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Request origin is not allowed.")

    expected = request.session.get(CSRF_SESSION_KEY)
    supplied = request.headers.get("x-csrf-token")
    if not expected or not supplied or not secrets.compare_digest(expected, supplied):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "The page token is missing or expired.")
