"""Admin dashboard schema additions (feature/admin-ingredient-dashboard).

These tables live in the SAME SQLite database as the existing pricing
reference store (settings.price_db_path) -- there is no separate admin
database. This is a deliberate architecture decision: CLAUDE.md/the
ticket forbid a parallel ingredient/pricing database, and reusing the
one connection/schema mechanism the project already has
(app.db.connection, app.db.schema.create_schema) keeps this additive
rather than parallel.

Architecture note (read before touching canonical_ingredients /
ingredient_aliases): the LIVE recommendation/autocomplete path does
NOT read canonical ingredient identity or aliases from the database at
all today. It reads two disconnected Python module-level constants --
app.domain.canonical_ingredients (a tiny PP-001 seed) and
app.domain.grocery_taxonomy (the larger LuLu-derived taxonomy used by
autocomplete and grocery ingestion). The `ingredient_aliases` table
below already existed in app.db.schema before this ticket but was
never read by any runtime code path (grep-verified) -- this migration
finally makes it a real, used table, and adds `canonical_ingredients`
as genuinely new (no DB table for canonical identity existed before).

Consequence, stated plainly for whoever reviews this: creating or
editing a canonical ingredient / alias through this admin dashboard
updates these DB tables, which the admin UI reads back from (so the
dashboard is fully self-consistent), but it does NOT retroactively
change what the live pantry-matching/autocomplete/normalization code
resolves, because that code still reads the Python constants, not
these tables. Rewiring app.domain.ingredient_normalizer /
app.domain.ingredient_autocomplete to read from SQLite instead would be
a real architecture change to Module A/B's frozen deterministic core
(DEC-006) and is explicitly out of scope for this ticket -- it was not
authorized and is not done here. See docs/admin/ADMIN_DASHBOARD.md
"Known Limitations" for the exact statement of this boundary.

Price management has no such gap: `ingredient_prices` and
`manual_price_entries` are already the real tables PriceRepository
reads at runtime (DEC-013), so admin price edits to
manual_price_entries have immediate, real effect on the live cost
engine, exactly as the ticket asks. `ingredient_prices` (the
LuLu-derived, median-aggregated table) is admin-*viewable* only here,
never hand-edited -- editing it by hand would silently violate its own
documented aggregation provenance (contributor_count,
aggregation_basis), which DEC-013 reserves for the deterministic
ingestion pipeline alone.
"""

from __future__ import annotations

import sqlite3

ADMIN_SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS canonical_ingredients (
        canonical_id TEXT PRIMARY KEY,
        display_name TEXT NOT NULL,
        default_unit TEXT,
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        updated_by TEXT NOT NULL,
        CHECK (status IN ('active', 'archived'))
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_canonical_ingredients_display_name
        ON canonical_ingredients(display_name)
    """,
    """
    CREATE TABLE IF NOT EXISTS admin_sessions (
        session_id TEXT PRIMARY KEY,
        admin_username TEXT NOT NULL,
        csrf_token TEXT NOT NULL,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        revoked_at TEXT
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_admin_sessions_expires
        ON admin_sessions(expires_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS admin_audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        occurred_at TEXT NOT NULL,
        admin_username TEXT NOT NULL,
        action TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        summary TEXT NOT NULL,
        request_id TEXT
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_admin_audit_log_entity
        ON admin_audit_log(entity_type, entity_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_admin_audit_log_occurred_at
        ON admin_audit_log(occurred_at)
    """,
)

# Additive columns on tables that predate this ticket. Applied via
# PRAGMA table_info + ALTER TABLE ... ADD COLUMN (idempotent, safe to
# run against an existing production database -- never drops or
# rewrites existing rows). ingredient_aliases/manual_price_entries
# both predate this ticket; both get a soft-delete/deactivate flag
# instead of ever supporting a hard DELETE from the admin UI (ticket
# section 18).
_ADDITIVE_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("ingredient_aliases", "active", "INTEGER NOT NULL DEFAULT 1"),
    ("ingredient_aliases", "updated_at", "TEXT"),
    ("ingredient_aliases", "updated_by", "TEXT"),
    ("manual_price_entries", "active", "INTEGER NOT NULL DEFAULT 1"),
    ("manual_price_entries", "updated_at", "TEXT"),
    ("manual_price_entries", "updated_by", "TEXT"),
)


def _existing_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    cursor = connection.execute(f"PRAGMA table_info({table})")
    return {row["name"] for row in cursor.fetchall()}


def _migrate_additive_columns(connection: sqlite3.Connection) -> None:
    for table, column, ddl in _ADDITIVE_COLUMNS:
        existing = _existing_columns(connection, table)
        if column not in existing:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def create_admin_schema(connection: sqlite3.Connection) -> None:
    """Idempotent: safe to run repeatedly and safe to run against a
    production database that already has the base PP-003 schema
    (app.db.schema.create_schema) applied. Never drops or truncates
    anything."""

    for statement in ADMIN_SCHEMA_STATEMENTS:
        connection.execute(statement)
    _migrate_additive_columns(connection)
    connection.commit()
