"""Admin CRUD over canonical_ingredients + ingredient_aliases
(feature/admin-ingredient-dashboard).

See app.db.admin_schema's module docstring for the important
architecture boundary: these tables are administrative records read
back by this same admin dashboard, not (yet) the source the live
pantry-matching/autocomplete path resolves against.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from app.admin.errors import AdminConflictError, AdminNotFoundError
from app.db.connection import connection_scope

_CANONICAL_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_MAX_DISPLAY_NAME_LENGTH = 120
_MAX_ALIAS_LENGTH = 120


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_alias_text(raw: str) -> str:
    """Case-normalized, trimmed, whitespace-collapsed comparison key --
    deliberately the same cleaning shape app.domain.ingredient_normalizer
    already applies to raw ingredient text, kept as an independent local
    implementation since that module's _clean() is a private helper of
    a frozen Module A/B file this ticket must not modify."""

    return re.sub(r"\s+", " ", raw.strip().lower())


def validate_canonical_id(canonical_id: str) -> None:
    if not _CANONICAL_ID_PATTERN.match(canonical_id):
        raise AdminConflictError(
            "canonical_id must be lowercase snake_case, start with a letter, and be 2-64 characters "
            "(e.g. 'bell_pepper')"
        )


@dataclass(frozen=True)
class CanonicalIngredientRecord:
    canonical_id: str
    display_name: str
    default_unit: str | None
    status: str
    created_at: str
    updated_at: str
    updated_by: str
    alias_count: int = 0
    has_manual_price: bool = False
    has_reference_price: bool = False


@dataclass(frozen=True)
class IngredientAliasRecord:
    alias: str
    canonical_id: str
    source: str
    confidence: float
    active: bool
    updated_at: str | None
    updated_by: str | None


class AdminIngredientRepository:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    # -- canonical ingredients -------------------------------------------------

    def list_ingredients(
        self, *, q: str | None = None, status: str | None = None, page: int = 1, page_size: int = 25
    ) -> tuple[list[CanonicalIngredientRecord], int]:
        bounded_page = max(1, page)
        bounded_page_size = max(1, min(page_size, 100))
        offset = (bounded_page - 1) * bounded_page_size

        where_clauses: list[str] = []
        params: list[object] = []
        if status is not None:
            where_clauses.append("ci.status = ?")
            params.append(status)
        if q:
            cleaned = normalize_alias_text(q)
            where_clauses.append(
                "(LOWER(ci.canonical_id) LIKE ? OR LOWER(ci.display_name) LIKE ? OR ci.canonical_id IN "
                "(SELECT canonical_id FROM ingredient_aliases WHERE alias LIKE ? AND active = 1))"
            )
            like = f"%{cleaned}%"
            params.extend([like, like, like])
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        with connection_scope(self._db_path, read_only=False) as connection:
            total = connection.execute(
                f"SELECT COUNT(*) AS c FROM canonical_ingredients ci {where_sql}", params
            ).fetchone()["c"]

            rows = connection.execute(
                f"""
                SELECT
                    ci.*,
                    (SELECT COUNT(*) FROM ingredient_aliases a WHERE a.canonical_id = ci.canonical_id AND a.active = 1)
                        AS alias_count,
                    EXISTS(SELECT 1 FROM manual_price_entries m WHERE m.canonical_id = ci.canonical_id AND m.active = 1)
                        AS has_manual_price,
                    EXISTS(SELECT 1 FROM ingredient_prices p WHERE p.canonical_id = ci.canonical_id)
                        AS has_reference_price
                FROM canonical_ingredients ci
                {where_sql}
                ORDER BY ci.display_name ASC
                LIMIT ? OFFSET ?
                """,
                [*params, bounded_page_size, offset],
            ).fetchall()

        return [self._row_to_record(row) for row in rows], total

    def get_ingredient(self, canonical_id: str) -> CanonicalIngredientRecord | None:
        with connection_scope(self._db_path, read_only=False) as connection:
            row = connection.execute(
                """
                SELECT
                    ci.*,
                    (SELECT COUNT(*) FROM ingredient_aliases a WHERE a.canonical_id = ci.canonical_id AND a.active = 1)
                        AS alias_count,
                    EXISTS(SELECT 1 FROM manual_price_entries m WHERE m.canonical_id = ci.canonical_id AND m.active = 1)
                        AS has_manual_price,
                    EXISTS(SELECT 1 FROM ingredient_prices p WHERE p.canonical_id = ci.canonical_id)
                        AS has_reference_price
                FROM canonical_ingredients ci WHERE ci.canonical_id = ?
                """,
                (canonical_id,),
            ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def create_ingredient(
        self, *, canonical_id: str, display_name: str, default_unit: str | None, updated_by: str
    ) -> CanonicalIngredientRecord:
        validate_canonical_id(canonical_id)
        display_name = display_name.strip()
        if not display_name or len(display_name) > _MAX_DISPLAY_NAME_LENGTH:
            raise AdminConflictError(f"display_name must be 1-{_MAX_DISPLAY_NAME_LENGTH} characters")

        now = _now_iso()
        with connection_scope(self._db_path, read_only=False) as connection:
            existing = connection.execute(
                "SELECT 1 FROM canonical_ingredients WHERE canonical_id = ?", (canonical_id,)
            ).fetchone()
            if existing is not None:
                # Never silently overwrite an existing ingredient (ticket section 10).
                raise AdminConflictError(f"canonical ingredient '{canonical_id}' already exists")
            connection.execute(
                """
                INSERT INTO canonical_ingredients
                    (canonical_id, display_name, default_unit, status, created_at, updated_at, updated_by)
                VALUES (?, ?, ?, 'active', ?, ?, ?)
                """,
                (canonical_id, display_name, default_unit, now, now, updated_by),
            )
            connection.commit()

        record = self.get_ingredient(canonical_id)
        assert record is not None
        return record

    def update_ingredient(
        self,
        canonical_id: str,
        *,
        display_name: str | None,
        default_unit: str | None,
        status: str | None,
        updated_by: str,
    ) -> CanonicalIngredientRecord:
        # canonical_id itself is immutable by design (ticket section 11):
        # it is the join key both ingredient_aliases and
        # manual_price_entries/ingredient_prices key their rows against,
        # so an arbitrary rename would silently orphan every dependent
        # row. There is no field/route to change it.
        existing = self.get_ingredient(canonical_id)
        if existing is None:
            raise AdminNotFoundError(f"canonical ingredient '{canonical_id}' not found")

        if display_name is not None:
            display_name = display_name.strip()
            if not display_name or len(display_name) > _MAX_DISPLAY_NAME_LENGTH:
                raise AdminConflictError(f"display_name must be 1-{_MAX_DISPLAY_NAME_LENGTH} characters")
        if status is not None and status not in ("active", "archived"):
            raise AdminConflictError("status must be 'active' or 'archived'")

        new_display_name = display_name if display_name is not None else existing.display_name
        new_default_unit = default_unit if default_unit is not None else existing.default_unit
        new_status = status if status is not None else existing.status

        with connection_scope(self._db_path, read_only=False) as connection:
            connection.execute(
                """
                UPDATE canonical_ingredients
                SET display_name = ?, default_unit = ?, status = ?, updated_at = ?, updated_by = ?
                WHERE canonical_id = ?
                """,
                (new_display_name, new_default_unit, new_status, _now_iso(), updated_by, canonical_id),
            )
            connection.commit()

        record = self.get_ingredient(canonical_id)
        assert record is not None
        return record

    @staticmethod
    def _row_to_record(row) -> CanonicalIngredientRecord:
        return CanonicalIngredientRecord(
            canonical_id=row["canonical_id"],
            display_name=row["display_name"],
            default_unit=row["default_unit"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            updated_by=row["updated_by"],
            alias_count=row["alias_count"],
            has_manual_price=bool(row["has_manual_price"]),
            has_reference_price=bool(row["has_reference_price"]),
        )

    # -- aliases -----------------------------------------------------------

    def list_aliases(self, canonical_id: str, *, include_inactive: bool = False) -> list[IngredientAliasRecord]:
        with connection_scope(self._db_path, read_only=False) as connection:
            if include_inactive:
                rows = connection.execute(
                    "SELECT * FROM ingredient_aliases WHERE canonical_id = ? ORDER BY alias ASC",
                    (canonical_id,),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM ingredient_aliases WHERE canonical_id = ? AND active = 1 ORDER BY alias ASC",
                    (canonical_id,),
                ).fetchall()
        return [self._alias_row_to_record(row) for row in rows]

    def create_alias(
        self, *, canonical_id: str, alias_text: str, source: str, updated_by: str
    ) -> IngredientAliasRecord:
        cleaned = normalize_alias_text(alias_text)
        if not cleaned or len(cleaned) > _MAX_ALIAS_LENGTH:
            raise AdminConflictError(f"alias must be 1-{_MAX_ALIAS_LENGTH} characters")

        if self.get_ingredient(canonical_id) is None:
            raise AdminNotFoundError(f"canonical ingredient '{canonical_id}' not found")

        with connection_scope(self._db_path, read_only=False) as connection:
            existing = connection.execute(
                "SELECT canonical_id, active FROM ingredient_aliases WHERE alias = ?", (cleaned,)
            ).fetchone()
            if existing is not None and existing["active"]:
                if existing["canonical_id"] == canonical_id:
                    raise AdminConflictError(f"alias '{cleaned}' is already mapped to '{canonical_id}'")
                # A conflicting alias must never silently remap from one
                # canonical ingredient to another (ticket section 12).
                raise AdminConflictError(
                    f"alias '{cleaned}' is already mapped to a different canonical ingredient "
                    f"('{existing['canonical_id']}'); use the explicit reassignment workflow if this is intentional"
                )

            now = _now_iso()
            if existing is not None:
                # Previously deactivated alias for the same or a
                # different canonical id -- reactivate onto the
                # requested canonical_id rather than violating the
                # PRIMARY KEY with a second INSERT.
                connection.execute(
                    """
                    UPDATE ingredient_aliases
                    SET canonical_id = ?, source = ?, confidence = 1.0, active = 1, updated_at = ?, updated_by = ?
                    WHERE alias = ?
                    """,
                    (canonical_id, source, now, updated_by, cleaned),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO ingredient_aliases (alias, canonical_id, source, confidence, active, updated_at, updated_by)
                    VALUES (?, ?, ?, 1.0, 1, ?, ?)
                    """,
                    (cleaned, canonical_id, source, now, updated_by),
                )
            connection.commit()

        alias_record = self._get_alias(cleaned)
        assert alias_record is not None
        return alias_record

    def reassign_alias(self, alias_text: str, *, new_canonical_id: str, updated_by: str) -> IngredientAliasRecord:
        """Explicit corrective reassignment only (ticket section 12) --
        the API layer requires an explicit confirmation flag before
        calling this; this method itself performs the write
        unconditionally once called, exactly like update_ingredient."""

        cleaned = normalize_alias_text(alias_text)
        existing = self._get_alias(cleaned)
        if existing is None:
            raise AdminNotFoundError(f"alias '{cleaned}' not found")
        if self.get_ingredient(new_canonical_id) is None:
            raise AdminNotFoundError(f"canonical ingredient '{new_canonical_id}' not found")

        with connection_scope(self._db_path, read_only=False) as connection:
            connection.execute(
                "UPDATE ingredient_aliases SET canonical_id = ?, active = 1, updated_at = ?, updated_by = ? WHERE alias = ?",
                (new_canonical_id, _now_iso(), updated_by, cleaned),
            )
            connection.commit()

        record = self._get_alias(cleaned)
        assert record is not None
        return record

    def deactivate_alias(self, alias_text: str, *, updated_by: str) -> IngredientAliasRecord:
        cleaned = normalize_alias_text(alias_text)
        existing = self._get_alias(cleaned)
        if existing is None:
            raise AdminNotFoundError(f"alias '{cleaned}' not found")

        with connection_scope(self._db_path, read_only=False) as connection:
            connection.execute(
                "UPDATE ingredient_aliases SET active = 0, updated_at = ?, updated_by = ? WHERE alias = ?",
                (_now_iso(), updated_by, cleaned),
            )
            connection.commit()

        record = self._get_alias(cleaned)
        assert record is not None
        return record

    def _get_alias(self, cleaned_alias: str) -> IngredientAliasRecord | None:
        with connection_scope(self._db_path, read_only=False) as connection:
            row = connection.execute("SELECT * FROM ingredient_aliases WHERE alias = ?", (cleaned_alias,)).fetchone()
        return self._alias_row_to_record(row) if row is not None else None

    @staticmethod
    def _alias_row_to_record(row) -> IngredientAliasRecord:
        return IngredientAliasRecord(
            alias=row["alias"],
            canonical_id=row["canonical_id"],
            source=row["source"],
            confidence=row["confidence"],
            active=bool(row["active"]),
            updated_at=row["updated_at"],
            updated_by=row["updated_by"],
        )
