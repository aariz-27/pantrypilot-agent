"""FastAPI dependencies for admin session/CSRF enforcement and
repository wiring (ticket sections 6, 7, 30).

Every /api/admin/* route except login depends (directly or
transitively) on require_admin_session, so an unauthenticated direct
request to any admin endpoint fails independently of the frontend --
the frontend hiding /admin is never the only guard (ticket section 30).
"""

from __future__ import annotations

import hmac

from fastapi import Cookie, Depends, Header, Request

from app.admin.errors import AdminAuthError, AdminCsrfError, AdminNotConfiguredError
from app.admin.security import parse_session_cookie_value
from app.config import Settings, get_settings
from app.repositories.admin_audit_repository import AdminAuditRepository
from app.repositories.admin_ingredient_repository import AdminIngredientRepository
from app.repositories.admin_price_repository import AdminPriceRepository
from app.repositories.admin_session_repository import AdminSessionRecord, AdminSessionRepository

ADMIN_SESSION_COOKIE_NAME = "pp_admin_session"
ADMIN_CSRF_HEADER_NAME = "x-admin-csrf-token"


def get_admin_session_repository(settings: Settings = Depends(get_settings)) -> AdminSessionRepository:
    return AdminSessionRepository(settings.price_db_path)


def get_admin_audit_repository(settings: Settings = Depends(get_settings)) -> AdminAuditRepository:
    return AdminAuditRepository(settings.price_db_path)


def get_admin_ingredient_repository(settings: Settings = Depends(get_settings)) -> AdminIngredientRepository:
    return AdminIngredientRepository(settings.price_db_path)


def get_admin_price_repository(settings: Settings = Depends(get_settings)) -> AdminPriceRepository:
    return AdminPriceRepository(settings.price_db_path)


def require_admin_configured(settings: Settings = Depends(get_settings)) -> Settings:
    if not settings.admin_configured:
        raise AdminNotConfiguredError(
            "Admin dashboard is not configured on this deployment (missing PANTRYPILOT_ADMIN_* environment variables)"
        )
    return settings


def require_admin_session(
    request: Request,
    settings: Settings = Depends(require_admin_configured),
    session_repo: AdminSessionRepository = Depends(get_admin_session_repository),
    pp_admin_session: str | None = Cookie(default=None),
) -> AdminSessionRecord:
    if not pp_admin_session:
        raise AdminAuthError("Authentication required")

    session_secret = settings.admin_session_secret.get_secret_value() if settings.admin_session_secret else None
    if session_secret is None:
        raise AdminAuthError("Authentication required")

    session_id = parse_session_cookie_value(pp_admin_session, session_secret)
    if session_id is None:
        raise AdminAuthError("Authentication required")

    session = session_repo.get_active_session(session_id)
    if session is None:
        raise AdminAuthError("Authentication required")

    return session


def require_csrf(
    x_admin_csrf_token: str | None = Header(default=None, alias=ADMIN_CSRF_HEADER_NAME),
    session: AdminSessionRecord = Depends(require_admin_session),
) -> AdminSessionRecord:
    """Depend on this (instead of require_admin_session directly) from
    every mutating (POST/PATCH/DELETE) admin route. Double-submit-style
    CSRF: the token was handed to the frontend only in the login/session
    JSON response body (never in a readable cookie, never in
    localStorage -- ticket section 7), so an attacker who can only
    trigger a cross-site request (and therefore has the ambient
    HttpOnly session cookie sent automatically but no way to read the
    JSON response body) cannot supply a matching header value."""

    if not x_admin_csrf_token or not hmac.compare_digest(x_admin_csrf_token, session.csrf_token):
        raise AdminCsrfError("Missing or invalid CSRF token")
    return session
