"""GET /api/admin/dashboard/summary and read-only grocery product
inspection (ticket sections 16, 25).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.admin.deps import require_admin_session
from app.config import Settings, get_settings
from app.repositories.admin_dashboard_repository import AdminDashboardRepository
from app.repositories.admin_session_repository import AdminSessionRecord
from app.schemas.admin import AdminDashboardSummaryResponse, GroceryProductListResponse, GroceryProductResponse

router = APIRouter()


def get_admin_dashboard_repository(settings: Settings = Depends(get_settings)) -> AdminDashboardRepository:
    return AdminDashboardRepository(settings.price_db_path)


@router.get("/admin/dashboard/summary", response_model=AdminDashboardSummaryResponse)
def get_dashboard_summary(
    _session: AdminSessionRecord = Depends(require_admin_session),
    repo: AdminDashboardRepository = Depends(get_admin_dashboard_repository),
) -> AdminDashboardSummaryResponse:
    summary = repo.get_summary()
    return AdminDashboardSummaryResponse(
        canonical_ingredient_count=summary.canonical_ingredient_count,
        active_alias_count=summary.active_alias_count,
        ingredients_with_manual_price=summary.ingredients_with_manual_price,
        ingredients_without_known_price=summary.ingredients_without_known_price,
        mapped_product_count=summary.mapped_product_count,
        unmapped_product_count=summary.unmapped_product_count,
    )


@router.get("/admin/grocery/products", response_model=GroceryProductListResponse)
def list_grocery_products(
    status: str | None = Query(default=None, max_length=40),
    q: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    _session: AdminSessionRecord = Depends(require_admin_session),
    repo: AdminDashboardRepository = Depends(get_admin_dashboard_repository),
) -> GroceryProductListResponse:
    items, total = repo.list_grocery_products(status=status, q=q, page=page, page_size=page_size)
    return GroceryProductListResponse(
        items=[GroceryProductResponse(**item) for item in items], total=total, page=page, page_size=page_size
    )
