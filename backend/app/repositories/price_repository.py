"""M10: read-only SQLite-backed reference price lookup.

Runtime contract: given a canonical ingredient ID, return usable
deterministic price information or an explicit missing result. Never
accesses LuLu, never invokes an LLM, never returns zero for an unknown
price -- unknown is always None/not-found, exactly as
app.domain.models.CostEvaluation already requires upstream.

manual_price_entries is checked as a fallback when no LuLu-derived
reference exists, per DEC-013's small reviewed curated-fallback
allowance. Its rows are typed apart via source_type so callers can
always tell a LuLu-derived reference from a manual one.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.db.connection import connection_scope


@dataclass(frozen=True)
class PriceLookupResult:
    canonical_id: str
    normalized_unit: str
    normalized_price_per_unit: float
    package_quantity: float | None
    package_unit: str | None
    package_price_aed: float | None
    normalized_package_quantity: float | None
    contributor_count: int
    aggregation_basis: str
    source_name: str
    source_product_name: str | None
    source_url: str | None
    collected_at: str
    source_type: str  # "lulu_reference" | "manual_curated"


class PriceRepository:
    """Read-only. Opens its own read-only SQLite connection per call --
    this is a low-QPS reference lookup, not a hot path requiring a
    pooled connection."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    def get_price(self, canonical_id: str, normalized_unit: str | None = None) -> PriceLookupResult | None:
        with connection_scope(self._db_path, read_only=True) as connection:
            row = self._query_ingredient_prices(connection, canonical_id, normalized_unit)
            if row is not None:
                return PriceLookupResult(
                    canonical_id=row["canonical_id"],
                    normalized_unit=row["normalized_unit"],
                    normalized_price_per_unit=row["normalized_price_per_unit"],
                    package_quantity=row["package_quantity"],
                    package_unit=row["package_unit"],
                    package_price_aed=row["package_price_aed"],
                    normalized_package_quantity=row["normalized_package_quantity"],
                    contributor_count=row["contributor_count"],
                    aggregation_basis=row["aggregation_basis"],
                    source_name=row["source_name"],
                    source_product_name=row["source_product_name"],
                    source_url=row["source_url"],
                    collected_at=row["collected_at"],
                    source_type="lulu_reference",
                )

            manual_row = self._query_manual_entries(connection, canonical_id, normalized_unit)
            if manual_row is not None:
                return PriceLookupResult(
                    canonical_id=manual_row["canonical_id"],
                    normalized_unit=manual_row["normalized_unit"],
                    normalized_price_per_unit=manual_row["normalized_price_per_unit"],
                    package_quantity=manual_row["package_quantity"],
                    package_unit=manual_row["package_unit"],
                    package_price_aed=manual_row["package_price_aed"],
                    normalized_package_quantity=manual_row["normalized_package_quantity"],
                    contributor_count=1,
                    aggregation_basis="manual_curated",
                    source_name="manual_curated",
                    source_product_name=manual_row["provenance_note"],
                    source_url=None,
                    collected_at=manual_row["collected_at"],
                    source_type="manual_curated",
                )

        return None

    @staticmethod
    def _query_ingredient_prices(connection, canonical_id: str, normalized_unit: str | None):
        if normalized_unit is not None:
            cursor = connection.execute(
                "SELECT * FROM ingredient_prices WHERE canonical_id = ? AND normalized_unit = ?",
                (canonical_id, normalized_unit),
            )
        else:
            cursor = connection.execute(
                "SELECT * FROM ingredient_prices WHERE canonical_id = ? LIMIT 1",
                (canonical_id,),
            )
        return cursor.fetchone()

    @staticmethod
    def _query_manual_entries(connection, canonical_id: str, normalized_unit: str | None):
        if normalized_unit is not None:
            cursor = connection.execute(
                "SELECT * FROM manual_price_entries WHERE canonical_id = ? AND normalized_unit = ?",
                (canonical_id, normalized_unit),
            )
        else:
            cursor = connection.execute(
                "SELECT * FROM manual_price_entries WHERE canonical_id = ? LIMIT 1",
                (canonical_id,),
            )
        return cursor.fetchone()
