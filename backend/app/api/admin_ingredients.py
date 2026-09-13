"""Admin ingredient + alias CRUD routes (ticket sections 9, 10, 11, 12).

Every route depends on require_admin_session (reads) or require_csrf
(writes) so direct unauthenticated requests to /api/admin/ingredients/*
fail independently of the admin frontend (section 30).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.admin.deps import get_admin_audit_repository, get_admin_ingredient_repository, require_admin_session, require_csrf
from app.admin.errors import AdminConflictError, AdminNotFoundError
from app.repositories.admin_audit_repository import AdminAuditRepository
from app.repositories.admin_ingredient_repository import (
    AdminIngredientRepository,
    CanonicalIngredientRecord,
    EffectiveCatalogRecord,
    IngredientAliasRecord,
)
from app.repositories.admin_session_repository import AdminSessionRecord
from app.schemas.admin import (
    CanonicalIngredientCreateRequest,
    CanonicalIngredientListResponse,
    CanonicalIngredientResponse,
    CanonicalIngredientUpdateRequest,
    EffectiveIngredientListResponse,
    EffectiveIngredientResponse,
    IngredientAliasCreateRequest,
    IngredientAliasReassignRequest,
    IngredientAliasResponse,
)

router = APIRouter()


def _to_effective_response(record: EffectiveCatalogRecord) -> EffectiveIngredientResponse:
    return EffectiveIngredientResponse(
        canonical_id=record.canonical_id,
        display_name=record.display_name,
        source=record.source,
        status=record.status,
        alias_count=record.alias_count,
        has_manual_price=record.has_manual_price,
        has_reference_price=record.has_reference_price,
    )


def _to_ingredient_response(record: CanonicalIngredientRecord) -> CanonicalIngredientResponse:
    return CanonicalIngredientResponse(
        canonical_id=record.canonical_id,
        display_name=record.display_name,
        default_unit=record.default_unit,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
        updated_by=record.updated_by,
        alias_count=record.alias_count,
        has_manual_price=record.has_manual_price,
        has_reference_price=record.has_reference_price,
    )


def _to_alias_response(record: IngredientAliasRecord) -> IngredientAliasResponse:
    return IngredientAliasResponse(
        alias=record.alias,
        canonical_id=record.canonical_id,
        source=record.source,
        confidence=record.confidence,
        active=record.active,
        updated_at=record.updated_at,
        updated_by=record.updated_by,
    )


@router.get("/admin/catalog", response_model=EffectiveIngredientListResponse)
def list_effective_catalog(
    q: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    _session: AdminSessionRecord = Depends(require_admin_session),
    repo: AdminIngredientRepository = Depends(get_admin_ingredient_repository),
) -> EffectiveIngredientListResponse:
    # 2026-09-13 admin completion ticket: the EFFECTIVE catalog (built-in
    # + admin-managed merged), reusing the exact same merge the live app
    # resolves against (get_merged_vocabulary) -- never a second,
    # parallel taxonomy. GET /admin/ingredients below remains the
    # admin-DB-only CRUD surface, unchanged, for the existing
    # create/edit/alias/price management flows.
    items, total = repo.list_effective_catalog(q=q, page=page, page_size=page_size)
    return EffectiveIngredientListResponse(
        items=[_to_effective_response(i) for i in items], total=total, page=page, page_size=page_size
    )


@router.get("/admin/ingredients", response_model=CanonicalIngredientListResponse)
def list_ingredients(
    q: str | None = Query(default=None, max_length=120),
    status: str | None = Query(default=None, pattern="^(active|archived)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    _session: AdminSessionRecord = Depends(require_admin_session),
    repo: AdminIngredientRepository = Depends(get_admin_ingredient_repository),
) -> CanonicalIngredientListResponse:
    items, total = repo.list_ingredients(q=q, status=status, page=page, page_size=page_size)
    return CanonicalIngredientListResponse(
        items=[_to_ingredient_response(i) for i in items], total=total, page=page, page_size=page_size
    )


@router.post("/admin/ingredients", response_model=CanonicalIngredientResponse, status_code=201)
def create_ingredient(
    body: CanonicalIngredientCreateRequest,
    session: AdminSessionRecord = Depends(require_csrf),
    repo: AdminIngredientRepository = Depends(get_admin_ingredient_repository),
    audit_repo: AdminAuditRepository = Depends(get_admin_audit_repository),
) -> CanonicalIngredientResponse:
    record = repo.create_ingredient(
        canonical_id=body.canonical_id, display_name=body.display_name, default_unit=body.default_unit,
        updated_by=session.admin_username,
    )
    audit_repo.record(
        admin_username=session.admin_username, action="ingredient_created", entity_type="canonical_ingredient",
        entity_id=record.canonical_id, summary=f"display_name='{record.display_name}' default_unit={record.default_unit!r}",
    )
    return _to_ingredient_response(record)


@router.get("/admin/ingredients/{canonical_id}", response_model=CanonicalIngredientResponse)
def get_ingredient(
    canonical_id: str,
    _session: AdminSessionRecord = Depends(require_admin_session),
    repo: AdminIngredientRepository = Depends(get_admin_ingredient_repository),
) -> CanonicalIngredientResponse:
    record = repo.get_ingredient(canonical_id)
    if record is None:
        raise AdminNotFoundError(f"canonical ingredient '{canonical_id}' not found")
    return _to_ingredient_response(record)


@router.patch("/admin/ingredients/{canonical_id}", response_model=CanonicalIngredientResponse)
def update_ingredient(
    canonical_id: str,
    body: CanonicalIngredientUpdateRequest,
    session: AdminSessionRecord = Depends(require_csrf),
    repo: AdminIngredientRepository = Depends(get_admin_ingredient_repository),
    audit_repo: AdminAuditRepository = Depends(get_admin_audit_repository),
) -> CanonicalIngredientResponse:
    record = repo.update_ingredient(
        canonical_id, display_name=body.display_name, default_unit=body.default_unit, status=body.status,
        updated_by=session.admin_username,
    )
    changed_fields = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    audit_repo.record(
        admin_username=session.admin_username, action="ingredient_updated", entity_type="canonical_ingredient",
        entity_id=canonical_id, summary=f"changed_fields={changed_fields}",
    )
    return _to_ingredient_response(record)


@router.get("/admin/ingredients/{canonical_id}/aliases", response_model=list[IngredientAliasResponse])
def list_aliases(
    canonical_id: str,
    include_inactive: bool = Query(default=False),
    _session: AdminSessionRecord = Depends(require_admin_session),
    repo: AdminIngredientRepository = Depends(get_admin_ingredient_repository),
) -> list[IngredientAliasResponse]:
    return [_to_alias_response(a) for a in repo.list_aliases(canonical_id, include_inactive=include_inactive)]


@router.post("/admin/ingredients/{canonical_id}/aliases", response_model=IngredientAliasResponse, status_code=201)
def create_alias(
    canonical_id: str,
    body: IngredientAliasCreateRequest,
    session: AdminSessionRecord = Depends(require_csrf),
    repo: AdminIngredientRepository = Depends(get_admin_ingredient_repository),
    audit_repo: AdminAuditRepository = Depends(get_admin_audit_repository),
) -> IngredientAliasResponse:
    record = repo.create_alias(
        canonical_id=canonical_id, alias_text=body.alias, source=body.source, updated_by=session.admin_username
    )
    audit_repo.record(
        admin_username=session.admin_username, action="alias_created", entity_type="ingredient_alias",
        entity_id=record.alias, summary=f"canonical_id='{record.canonical_id}' source='{record.source}'",
    )
    return _to_alias_response(record)


@router.patch("/admin/aliases/{alias}", response_model=IngredientAliasResponse)
def reassign_alias(
    alias: str,
    body: IngredientAliasReassignRequest,
    session: AdminSessionRecord = Depends(require_csrf),
    repo: AdminIngredientRepository = Depends(get_admin_ingredient_repository),
    audit_repo: AdminAuditRepository = Depends(get_admin_audit_repository),
) -> IngredientAliasResponse:
    if not body.confirm_reassignment:
        raise AdminConflictError("confirm_reassignment must be true to reassign an alias to a different ingredient")

    record = repo.reassign_alias(alias, new_canonical_id=body.new_canonical_id, updated_by=session.admin_username)
    audit_repo.record(
        admin_username=session.admin_username, action="alias_reassigned", entity_type="ingredient_alias",
        entity_id=record.alias, summary=f"new_canonical_id='{record.canonical_id}'",
    )
    return _to_alias_response(record)


@router.delete("/admin/aliases/{alias}", response_model=IngredientAliasResponse)
def deactivate_alias(
    alias: str,
    session: AdminSessionRecord = Depends(require_csrf),
    repo: AdminIngredientRepository = Depends(get_admin_ingredient_repository),
    audit_repo: AdminAuditRepository = Depends(get_admin_audit_repository),
) -> IngredientAliasResponse:
    # Soft-delete only (ticket section 18) -- ingredient_aliases rows
    # are never hard-deleted from the admin UI, just marked inactive.
    record = repo.deactivate_alias(alias, updated_by=session.admin_username)
    audit_repo.record(
        admin_username=session.admin_username, action="alias_deleted", entity_type="ingredient_alias",
        entity_id=record.alias, summary=f"deactivated, was mapped to '{record.canonical_id}'",
    )
    return _to_alias_response(record)
