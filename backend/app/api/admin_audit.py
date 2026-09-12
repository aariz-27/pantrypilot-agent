"""GET /api/admin/audit (ticket section 17). Read-only, still requires
an authenticated admin session -- audit history is itself sensitive
operational data.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.admin.deps import get_admin_audit_repository, require_admin_session
from app.repositories.admin_audit_repository import AdminAuditRepository
from app.repositories.admin_session_repository import AdminSessionRecord
from app.schemas.admin import AdminAuditEntryResponse, AdminAuditListResponse

router = APIRouter()


@router.get("/admin/audit", response_model=AdminAuditListResponse)
def list_audit_entries(
    entity_type: str | None = Query(default=None, max_length=60),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    _session: AdminSessionRecord = Depends(require_admin_session),
    repo: AdminAuditRepository = Depends(get_admin_audit_repository),
) -> AdminAuditListResponse:
    entries, total = repo.list_entries(entity_type=entity_type, page=page, page_size=page_size)
    return AdminAuditListResponse(
        items=[
            AdminAuditEntryResponse(
                id=e.id, occurred_at=e.occurred_at, admin_username=e.admin_username, action=e.action,
                entity_type=e.entity_type, entity_id=e.entity_id, summary=e.summary, request_id=e.request_id,
            )
            for e in entries
        ],
        total=total, page=page, page_size=page_size,
    )
