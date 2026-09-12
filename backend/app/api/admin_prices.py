"""Admin pricing routes (ticket sections 13, 14, 15). Reference prices
(ingredient_prices) are read-only here; manual_price_entries is the
only table these routes write to -- see
app.repositories.admin_price_repository's module docstring.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.admin.deps import get_admin_audit_repository, get_admin_price_repository, require_admin_session, require_csrf
from app.repositories.admin_audit_repository import AdminAuditRepository
from app.repositories.admin_price_repository import AdminPriceRepository, ManualPriceRecord, ReferencePriceRecord
from app.repositories.admin_session_repository import AdminSessionRecord
from app.schemas.admin import (
    IngredientPricesResponse,
    ManualPriceCreateRequest,
    ManualPriceResponse,
    ManualPriceUpdateRequest,
    ReferencePriceResponse,
)

router = APIRouter()


def _to_reference_response(record: ReferencePriceRecord) -> ReferencePriceResponse:
    return ReferencePriceResponse(
        canonical_id=record.canonical_id, normalized_unit=record.normalized_unit, display_name=record.display_name,
        normalized_price_per_unit=record.normalized_price_per_unit, package_quantity=record.package_quantity,
        package_unit=record.package_unit, package_price_aed=record.package_price_aed,
        contributor_count=record.contributor_count, aggregation_basis=record.aggregation_basis,
        source_name=record.source_name, collected_at=record.collected_at,
    )


def _to_manual_response(record: ManualPriceRecord) -> ManualPriceResponse:
    return ManualPriceResponse(
        canonical_id=record.canonical_id, normalized_unit=record.normalized_unit, display_name=record.display_name,
        normalized_price_per_unit=record.normalized_price_per_unit, package_quantity=record.package_quantity,
        package_unit=record.package_unit, package_price_aed=record.package_price_aed,
        normalized_package_quantity=record.normalized_package_quantity, source_type=record.source_type,
        provenance_note=record.provenance_note, collected_at=record.collected_at, active=record.active,
        updated_at=record.updated_at, updated_by=record.updated_by,
    )


@router.get("/admin/ingredients/{canonical_id}/prices", response_model=IngredientPricesResponse)
def get_ingredient_prices(
    canonical_id: str,
    _session: AdminSessionRecord = Depends(require_admin_session),
    repo: AdminPriceRepository = Depends(get_admin_price_repository),
) -> IngredientPricesResponse:
    return IngredientPricesResponse(
        reference_prices=[_to_reference_response(r) for r in repo.list_reference_prices(canonical_id)],
        manual_prices=[_to_manual_response(r) for r in repo.list_manual_prices(canonical_id)],
    )


@router.post("/admin/ingredients/{canonical_id}/prices", response_model=ManualPriceResponse, status_code=201)
def create_manual_price(
    canonical_id: str,
    body: ManualPriceCreateRequest,
    session: AdminSessionRecord = Depends(require_csrf),
    repo: AdminPriceRepository = Depends(get_admin_price_repository),
    audit_repo: AdminAuditRepository = Depends(get_admin_audit_repository),
) -> ManualPriceResponse:
    record = repo.create_manual_price(
        canonical_id=canonical_id, normalized_unit=body.normalized_unit, display_name=body.display_name,
        normalized_price_per_unit=body.normalized_price_per_unit, package_quantity=body.package_quantity,
        package_unit=body.package_unit, package_price_aed=body.package_price_aed,
        normalized_package_quantity=body.normalized_package_quantity, provenance_note=body.provenance_note,
        updated_by=session.admin_username,
    )
    audit_repo.record(
        admin_username=session.admin_username, action="price_created", entity_type="manual_price_entry",
        entity_id=f"{canonical_id}:{body.normalized_unit}",
        summary=f"normalized_price_per_unit={record.normalized_price_per_unit}",
    )
    return _to_manual_response(record)


@router.patch("/admin/prices/{canonical_id}/{normalized_unit}", response_model=ManualPriceResponse)
def update_manual_price(
    canonical_id: str,
    normalized_unit: str,
    body: ManualPriceUpdateRequest,
    session: AdminSessionRecord = Depends(require_csrf),
    repo: AdminPriceRepository = Depends(get_admin_price_repository),
    audit_repo: AdminAuditRepository = Depends(get_admin_audit_repository),
) -> ManualPriceResponse:
    record = repo.update_manual_price(
        canonical_id, normalized_unit, display_name=body.display_name,
        normalized_price_per_unit=body.normalized_price_per_unit, package_quantity=body.package_quantity,
        package_unit=body.package_unit, package_price_aed=body.package_price_aed,
        normalized_package_quantity=body.normalized_package_quantity, provenance_note=body.provenance_note,
        updated_by=session.admin_username,
    )
    changed_fields = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    audit_repo.record(
        admin_username=session.admin_username, action="price_updated", entity_type="manual_price_entry",
        entity_id=f"{canonical_id}:{normalized_unit}", summary=f"changed_fields={changed_fields}",
    )
    return _to_manual_response(record)


@router.delete("/admin/prices/{canonical_id}/{normalized_unit}", response_model=ManualPriceResponse)
def deactivate_manual_price(
    canonical_id: str,
    normalized_unit: str,
    session: AdminSessionRecord = Depends(require_csrf),
    repo: AdminPriceRepository = Depends(get_admin_price_repository),
    audit_repo: AdminAuditRepository = Depends(get_admin_audit_repository),
) -> ManualPriceResponse:
    record = repo.deactivate_manual_price(canonical_id, normalized_unit, updated_by=session.admin_username)
    audit_repo.record(
        admin_username=session.admin_username, action="price_deactivated", entity_type="manual_price_entry",
        entity_id=f"{canonical_id}:{normalized_unit}", summary="deactivated",
    )
    return _to_manual_response(record)
