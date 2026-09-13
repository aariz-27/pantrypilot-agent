"""Cheap, accurate summary counts for the admin dashboard home (ticket
section 25). Every figure here is a direct COUNT/EXISTS query over
already-indexed columns -- no full-table scan of grocery products, no
fabricated/estimated analytics.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.db.connection import connection_scope
from app.domain.grocery_models import MappingStatus
from app.repositories.runtime_ingredient_repository import get_merged_vocabulary


@dataclass(frozen=True)
class AdminDashboardSummary:
    canonical_ingredient_count: int
    active_alias_count: int
    ingredients_with_manual_price: int
    ingredients_without_known_price: int
    mapped_product_count: int
    unmapped_product_count: int
    # 2026-09-13 admin completion ticket (section 4, status/usability):
    # the FULL effective catalog size (built-in + admin merged, via the
    # same get_merged_vocabulary the live app resolves against) --
    # distinct from canonical_ingredient_count above, which only counts
    # admin-managed rows.
    effective_ingredient_count: int


class AdminDashboardRepository:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    def get_summary(self) -> AdminDashboardSummary:
        with connection_scope(self._db_path, read_only=False) as connection:
            canonical_ingredient_count = connection.execute(
                "SELECT COUNT(*) AS c FROM canonical_ingredients WHERE status = 'active'"
            ).fetchone()["c"]
            active_alias_count = connection.execute(
                "SELECT COUNT(*) AS c FROM ingredient_aliases WHERE active = 1"
            ).fetchone()["c"]
            ingredients_with_manual_price = connection.execute(
                "SELECT COUNT(DISTINCT canonical_id) AS c FROM manual_price_entries WHERE active = 1"
            ).fetchone()["c"]
            ingredients_without_known_price = connection.execute(
                """
                SELECT COUNT(*) AS c FROM canonical_ingredients ci
                WHERE ci.status = 'active'
                  AND NOT EXISTS (SELECT 1 FROM ingredient_prices p WHERE p.canonical_id = ci.canonical_id)
                  AND NOT EXISTS (
                      SELECT 1 FROM manual_price_entries m WHERE m.canonical_id = ci.canonical_id AND m.active = 1
                  )
                """
            ).fetchone()["c"]
            mapped_product_count = connection.execute(
                "SELECT COUNT(*) AS c FROM mapped_grocery_products WHERE mapping_status = ?",
                (MappingStatus.MAPPED.value,),
            ).fetchone()["c"]
            unmapped_product_count = connection.execute(
                "SELECT COUNT(*) AS c FROM mapped_grocery_products WHERE mapping_status = ?",
                (MappingStatus.UNMAPPED_INGREDIENT.value,),
            ).fetchone()["c"]

        effective_ingredient_count = len(get_merged_vocabulary(self._db_path).canonical_ids)

        return AdminDashboardSummary(
            canonical_ingredient_count=canonical_ingredient_count,
            active_alias_count=active_alias_count,
            ingredients_with_manual_price=ingredients_with_manual_price,
            ingredients_without_known_price=ingredients_without_known_price,
            mapped_product_count=mapped_product_count,
            unmapped_product_count=unmapped_product_count,
            effective_ingredient_count=effective_ingredient_count,
        )

    def list_grocery_products(
        self, *, status: str | None = None, q: str | None = None, page: int = 1, page_size: int = 25
    ) -> tuple[list[dict], int]:
        """Read-only inspection over mapped_grocery_products (ticket
        section 16) -- no destructive bulk remapping, no write path at
        all. `status` is one of app.domain.grocery_models.MappingStatus.
        """

        bounded_page = max(1, page)
        bounded_page_size = max(1, min(page_size, 100))
        offset = (bounded_page - 1) * bounded_page_size

        where_clauses: list[str] = []
        params: list[object] = []
        if status is not None:
            where_clauses.append("mapping_status = ?")
            params.append(status)
        if q:
            where_clauses.append("LOWER(title) LIKE ?")
            params.append(f"%{q.strip().lower()}%")
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        with connection_scope(self._db_path, read_only=False) as connection:
            total = connection.execute(
                f"SELECT COUNT(*) AS c FROM mapped_grocery_products {where_sql}", params
            ).fetchone()["c"]
            rows = connection.execute(
                f"""
                SELECT id, title, brand, canonical_id, mapping_status, rejection_reason,
                       normalized_price_per_unit, normalized_unit, product_type
                FROM mapped_grocery_products
                {where_sql}
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                [*params, bounded_page_size, offset],
            ).fetchall()

        items = [
            {
                "id": row["id"],
                "title": row["title"],
                "brand": row["brand"],
                "canonical_id": row["canonical_id"],
                "mapping_status": row["mapping_status"],
                "rejection_reason": row["rejection_reason"],
                "normalized_price_per_unit": row["normalized_price_per_unit"],
                "normalized_unit": row["normalized_unit"],
                "product_type": row["product_type"],
            }
            for row in rows
        ]
        return items, total
