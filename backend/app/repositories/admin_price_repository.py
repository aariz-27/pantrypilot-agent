"""Admin read/write access to the pricing reference store
(feature/admin-ingredient-dashboard).

`ingredient_prices` (LuLu-derived, median-aggregated per DEC-013) is
READ-ONLY here -- admin edits never touch it, preserving its documented
aggregation provenance. `manual_price_entries` is the one table this
ticket's "add/update manual price" capability writes to; it is exactly
the table DEC-013 already designed for a small, explicitly reviewed
curated fallback, so this does not introduce a competing pricing
mechanism (ticket section 13/15). PriceRepository.get_price's existing
precedence (ingredient_prices first, manual_price_entries fallback) is
untouched and unread by this module -- this module only writes rows,
the live cost engine still resolves precedence exactly as before.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

from app.admin.errors import AdminConflictError, AdminNotFoundError, AdminValidationError
from app.db.connection import connection_scope

# Deliberately matches the normalized units actually produced by the
# real ingestion pipeline (CURRENT_STATUS.md PP-003 QA table: g/ml/pcs
# only) -- not an arbitrary invented list. A manual entry in any other
# unit could never be compared against/overridden-by a real
# ingredient_prices row for the same canonical_id.
ALLOWED_NORMALIZED_UNITS: frozenset[str] = frozenset({"g", "ml", "pcs"})
_MAX_PROVENANCE_NOTE_LENGTH = 500
_MAX_DISPLAY_NAME_LENGTH = 120


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_positive_finite(value: float, field_name: str) -> None:
    # Never silently treat missing/unknown price as zero (DEC-007) --
    # this rejects exactly the invalid numeric shapes that would let a
    # bad value slip past into a real cost calculation: negative, zero,
    # NaN, and +/-infinity.
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise AdminValidationError(f"{field_name} must be a number")
    if math.isnan(value) or math.isinf(value):
        raise AdminValidationError(f"{field_name} must be a finite number")
    if value <= 0:
        raise AdminValidationError(f"{field_name} must be greater than zero")


@dataclass(frozen=True)
class ManualPriceRecord:
    canonical_id: str
    normalized_unit: str
    display_name: str
    normalized_price_per_unit: float
    package_quantity: float | None
    package_unit: str | None
    package_price_aed: float | None
    normalized_package_quantity: float | None
    source_type: str
    provenance_note: str
    collected_at: str
    active: bool
    updated_at: str | None
    updated_by: str | None


@dataclass(frozen=True)
class ReferencePriceRecord:
    canonical_id: str
    normalized_unit: str
    display_name: str
    normalized_price_per_unit: float
    package_quantity: float | None
    package_unit: str | None
    package_price_aed: float | None
    contributor_count: int
    aggregation_basis: str
    source_name: str
    collected_at: str


class AdminPriceRepository:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    def list_reference_prices(self, canonical_id: str) -> list[ReferencePriceRecord]:
        with connection_scope(self._db_path, read_only=False) as connection:
            rows = connection.execute(
                "SELECT * FROM ingredient_prices WHERE canonical_id = ? ORDER BY normalized_unit", (canonical_id,)
            ).fetchall()
        return [
            ReferencePriceRecord(
                canonical_id=row["canonical_id"],
                normalized_unit=row["normalized_unit"],
                display_name=row["display_name"],
                normalized_price_per_unit=row["normalized_price_per_unit"],
                package_quantity=row["package_quantity"],
                package_unit=row["package_unit"],
                package_price_aed=row["package_price_aed"],
                contributor_count=row["contributor_count"],
                aggregation_basis=row["aggregation_basis"],
                source_name=row["source_name"],
                collected_at=row["collected_at"],
            )
            for row in rows
        ]

    def list_manual_prices(self, canonical_id: str, *, include_inactive: bool = False) -> list[ManualPriceRecord]:
        with connection_scope(self._db_path, read_only=False) as connection:
            if include_inactive:
                rows = connection.execute(
                    "SELECT * FROM manual_price_entries WHERE canonical_id = ? ORDER BY normalized_unit",
                    (canonical_id,),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM manual_price_entries WHERE canonical_id = ? AND active = 1 ORDER BY normalized_unit",
                    (canonical_id,),
                ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def create_manual_price(
        self,
        *,
        canonical_id: str,
        normalized_unit: str,
        display_name: str,
        normalized_price_per_unit: float,
        package_quantity: float | None,
        package_unit: str | None,
        package_price_aed: float | None,
        normalized_package_quantity: float | None,
        provenance_note: str,
        updated_by: str,
    ) -> ManualPriceRecord:
        if normalized_unit not in ALLOWED_NORMALIZED_UNITS:
            raise AdminValidationError(f"normalized_unit must be one of {sorted(ALLOWED_NORMALIZED_UNITS)}")
        display_name = display_name.strip()
        if not display_name or len(display_name) > _MAX_DISPLAY_NAME_LENGTH:
            raise AdminValidationError(f"display_name must be 1-{_MAX_DISPLAY_NAME_LENGTH} characters")
        provenance_note = provenance_note.strip()
        if not provenance_note or len(provenance_note) > _MAX_PROVENANCE_NOTE_LENGTH:
            raise AdminValidationError(f"provenance_note must be 1-{_MAX_PROVENANCE_NOTE_LENGTH} characters")

        _validate_positive_finite(normalized_price_per_unit, "normalized_price_per_unit")
        if package_quantity is not None:
            _validate_positive_finite(package_quantity, "package_quantity")
        if package_price_aed is not None:
            _validate_positive_finite(package_price_aed, "package_price_aed")
        if normalized_package_quantity is not None:
            _validate_positive_finite(normalized_package_quantity, "normalized_package_quantity")

        now = _now_iso()
        with connection_scope(self._db_path, read_only=False) as connection:
            existing = connection.execute(
                "SELECT active FROM manual_price_entries WHERE canonical_id = ? AND normalized_unit = ?",
                (canonical_id, normalized_unit),
            ).fetchone()
            if existing is not None and existing["active"]:
                # Never silently overwrite (ticket section 10's rule
                # applies equally to prices) -- use the PATCH/update path.
                raise AdminConflictError(
                    f"an active manual price already exists for ('{canonical_id}', '{normalized_unit}'); update it instead"
                )
            if existing is not None:
                connection.execute(
                    """
                    UPDATE manual_price_entries
                    SET display_name = ?, normalized_price_per_unit = ?, package_quantity = ?, package_unit = ?,
                        package_price_aed = ?, normalized_package_quantity = ?, provenance_note = ?,
                        active = 1, collected_at = ?, updated_at = ?, updated_by = ?
                    WHERE canonical_id = ? AND normalized_unit = ?
                    """,
                    (
                        display_name, normalized_price_per_unit, package_quantity, package_unit,
                        package_price_aed, normalized_package_quantity, provenance_note,
                        now, now, updated_by, canonical_id, normalized_unit,
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO manual_price_entries (
                        canonical_id, normalized_unit, display_name, normalized_price_per_unit,
                        package_quantity, package_unit, package_price_aed, normalized_package_quantity,
                        source_type, provenance_note, collected_at, active, updated_at, updated_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'manual_curated', ?, ?, 1, ?, ?)
                    """,
                    (
                        canonical_id, normalized_unit, display_name, normalized_price_per_unit,
                        package_quantity, package_unit, package_price_aed, normalized_package_quantity,
                        provenance_note, now, now, updated_by,
                    ),
                )
            connection.commit()

        record = self._get(canonical_id, normalized_unit)
        assert record is not None
        return record

    def update_manual_price(
        self,
        canonical_id: str,
        normalized_unit: str,
        *,
        display_name: str | None,
        normalized_price_per_unit: float | None,
        package_quantity: float | None,
        package_unit: str | None,
        package_price_aed: float | None,
        normalized_package_quantity: float | None,
        provenance_note: str | None,
        updated_by: str,
    ) -> ManualPriceRecord:
        existing = self._get(canonical_id, normalized_unit)
        if existing is None:
            raise AdminNotFoundError(f"manual price entry for ('{canonical_id}', '{normalized_unit}') not found")

        new_display_name = display_name.strip() if display_name is not None else existing.display_name
        if not new_display_name or len(new_display_name) > _MAX_DISPLAY_NAME_LENGTH:
            raise AdminValidationError(f"display_name must be 1-{_MAX_DISPLAY_NAME_LENGTH} characters")

        new_price = normalized_price_per_unit if normalized_price_per_unit is not None else existing.normalized_price_per_unit
        _validate_positive_finite(new_price, "normalized_price_per_unit")

        new_package_quantity = package_quantity if package_quantity is not None else existing.package_quantity
        if new_package_quantity is not None:
            _validate_positive_finite(new_package_quantity, "package_quantity")
        new_package_price = package_price_aed if package_price_aed is not None else existing.package_price_aed
        if new_package_price is not None:
            _validate_positive_finite(new_package_price, "package_price_aed")
        new_normalized_package_quantity = (
            normalized_package_quantity if normalized_package_quantity is not None else existing.normalized_package_quantity
        )
        if new_normalized_package_quantity is not None:
            _validate_positive_finite(new_normalized_package_quantity, "normalized_package_quantity")

        new_provenance_note = provenance_note.strip() if provenance_note is not None else existing.provenance_note
        if not new_provenance_note or len(new_provenance_note) > _MAX_PROVENANCE_NOTE_LENGTH:
            raise AdminValidationError(f"provenance_note must be 1-{_MAX_PROVENANCE_NOTE_LENGTH} characters")

        new_package_unit = package_unit if package_unit is not None else existing.package_unit

        with connection_scope(self._db_path, read_only=False) as connection:
            connection.execute(
                """
                UPDATE manual_price_entries
                SET display_name = ?, normalized_price_per_unit = ?, package_quantity = ?, package_unit = ?,
                    package_price_aed = ?, normalized_package_quantity = ?, provenance_note = ?,
                    updated_at = ?, updated_by = ?
                WHERE canonical_id = ? AND normalized_unit = ?
                """,
                (
                    new_display_name, new_price, new_package_quantity, new_package_unit,
                    new_package_price, new_normalized_package_quantity, new_provenance_note,
                    _now_iso(), updated_by, canonical_id, normalized_unit,
                ),
            )
            connection.commit()

        record = self._get(canonical_id, normalized_unit)
        assert record is not None
        return record

    def deactivate_manual_price(self, canonical_id: str, normalized_unit: str, *, updated_by: str) -> ManualPriceRecord:
        existing = self._get(canonical_id, normalized_unit)
        if existing is None:
            raise AdminNotFoundError(f"manual price entry for ('{canonical_id}', '{normalized_unit}') not found")

        with connection_scope(self._db_path, read_only=False) as connection:
            connection.execute(
                "UPDATE manual_price_entries SET active = 0, updated_at = ?, updated_by = ? "
                "WHERE canonical_id = ? AND normalized_unit = ?",
                (_now_iso(), updated_by, canonical_id, normalized_unit),
            )
            connection.commit()

        record = self._get(canonical_id, normalized_unit)
        assert record is not None
        return record

    def _get(self, canonical_id: str, normalized_unit: str) -> ManualPriceRecord | None:
        with connection_scope(self._db_path, read_only=False) as connection:
            row = connection.execute(
                "SELECT * FROM manual_price_entries WHERE canonical_id = ? AND normalized_unit = ?",
                (canonical_id, normalized_unit),
            ).fetchone()
        return self._row_to_record(row) if row is not None else None

    @staticmethod
    def _row_to_record(row) -> ManualPriceRecord:
        return ManualPriceRecord(
            canonical_id=row["canonical_id"],
            normalized_unit=row["normalized_unit"],
            display_name=row["display_name"],
            normalized_price_per_unit=row["normalized_price_per_unit"],
            package_quantity=row["package_quantity"],
            package_unit=row["package_unit"],
            package_price_aed=row["package_price_aed"],
            normalized_package_quantity=row["normalized_package_quantity"],
            source_type=row["source_type"],
            provenance_note=row["provenance_note"],
            collected_at=row["collected_at"],
            active=bool(row["active"]),
            updated_at=row["updated_at"],
            updated_by=row["updated_by"],
        )
