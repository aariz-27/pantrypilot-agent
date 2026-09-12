"""POST /api/admin/auth/login, /logout, GET /api/admin/auth/session
(ticket sections 5, 6, 7, 8).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from app.admin.deps import (
    ADMIN_SESSION_COOKIE_NAME,
    get_admin_audit_repository,
    get_admin_session_repository,
    require_admin_configured,
    require_admin_session,
    require_csrf,
)
from app.admin.errors import AdminAuthError
from app.admin.security import (
    build_session_cookie_value,
    constant_time_username_equals,
    generate_csrf_token,
    generate_session_id,
    verify_password,
)
from app.config import Settings, get_settings
from app.rate_limit import limiter
from app.repositories.admin_audit_repository import AdminAuditRepository
from app.repositories.admin_session_repository import AdminSessionRecord, AdminSessionRepository
from app.schemas.admin import AdminLoginRequest, AdminSessionResponse

router = APIRouter()


def _set_session_cookie(response: Response, cookie_value: str, settings: Settings) -> None:
    response.set_cookie(
        key=ADMIN_SESSION_COOKIE_NAME,
        value=cookie_value,
        httponly=True,
        secure=settings.environment == "production",
        samesite="strict",
        path="/",
        max_age=settings.admin_session_ttl_minutes * 60,
    )


@router.post("/admin/auth/login", response_model=AdminSessionResponse)
@limiter.limit(lambda: get_settings().rate_limit_admin_login)
def admin_login(
    request: Request,  # required, by name, for slowapi's @limiter.limit decorator
    body: AdminLoginRequest,
    response: Response,
    settings: Settings = Depends(require_admin_configured),
    session_repo: AdminSessionRepository = Depends(get_admin_session_repository),
    audit_repo: AdminAuditRepository = Depends(get_admin_audit_repository),
) -> AdminSessionResponse:
    configured_username = settings.admin_username
    configured_hash = settings.admin_password_hash.get_secret_value() if settings.admin_password_hash else None
    assert configured_username is not None and configured_hash is not None  # guaranteed by require_admin_configured

    # Same generic failure for a wrong username, a wrong password, or
    # both -- never distinguishable by the caller (ticket section 8).
    username_ok = constant_time_username_equals(body.username, configured_username)
    password_ok = verify_password(body.password, configured_hash)
    if not (username_ok and password_ok):
        raise AdminAuthError("Invalid username or password")

    session_secret = settings.admin_session_secret.get_secret_value()
    session_id = generate_session_id()
    csrf_token = generate_csrf_token()
    session = session_repo.create_session(
        session_id, configured_username, csrf_token, settings.admin_session_ttl_minutes
    )
    _set_session_cookie(response, build_session_cookie_value(session_id, session_secret), settings)

    audit_repo.record(
        admin_username=configured_username,
        action="admin_login",
        entity_type="admin_session",
        entity_id=session_id,
        summary="Admin login succeeded",
    )

    return AdminSessionResponse(username=session.admin_username, csrf_token=session.csrf_token, expires_at=session.expires_at)


@router.get("/admin/auth/session", response_model=AdminSessionResponse)
def admin_session_status(session: AdminSessionRecord = Depends(require_admin_session)) -> AdminSessionResponse:
    return AdminSessionResponse(username=session.admin_username, csrf_token=session.csrf_token, expires_at=session.expires_at)


@router.post("/admin/auth/logout")
def admin_logout(
    response: Response,
    settings: Settings = Depends(get_settings),
    session: AdminSessionRecord = Depends(require_csrf),
    session_repo: AdminSessionRepository = Depends(get_admin_session_repository),
    audit_repo: AdminAuditRepository = Depends(get_admin_audit_repository),
) -> dict:
    session_repo.revoke_session(session.session_id)
    response.delete_cookie(key=ADMIN_SESSION_COOKIE_NAME, path="/", samesite="strict")
    audit_repo.record(
        admin_username=session.admin_username,
        action="admin_logout",
        entity_type="admin_session",
        entity_id=session.session_id,
        summary="Admin logout",
    )
    return {"status": "ok"}
