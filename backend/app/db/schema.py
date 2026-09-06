"""SQLite schema for the grocery pricing reference store (M10/M14).

Three-layer design, mandatory per PP-003's ticket:

- raw_grocery_products: verbatim staging, one row per scraped record,
  never mutated after import. Full provenance retained.
- mapped_grocery_products: deterministic parse/mapping outcome per raw
  row (brand, canonical ID, package quantity/unit, normalized price).
  Every row -- mapped or not -- is retained for auditability; nothing
  is silently dropped.
- ingredient_prices: the FINAL runtime reference table PriceRepository
  reads. One row per (canonical_id, normalized_unit) pair, selected via
  the median-of-compatible-contributors policy (DEC-013). Never written
  by the live recommendation path.

manual_price_entries supports a small, explicitly reviewed curated
fallback (DEC-013) for ingredients LuLu's export doesn't usefully cover
-- distinct source_type from LuLu-derived rows, never auto-populated.

ingredient_aliases matches TECHNICAL_SPEC.md's existing schema and
records provenance of which raw product text contributed to which
canonical ID (source="grocery_import" vs "manual").
"""

from __future__ import annotations

SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS raw_grocery_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        import_batch_id TEXT NOT NULL,
        source_name TEXT NOT NULL,
        source_product_id TEXT,
        sku TEXT,
        title TEXT NOT NULL,
        brand TEXT,
        content TEXT,
        price_raw REAL,
        retail_price_raw REAL,
        discount_amount_raw REAL,
        discount_ratio_raw REAL,
        currency_raw TEXT,
        category1 TEXT,
        category2 TEXT,
        category3 TEXT,
        product_type TEXT,
        in_stock INTEGER,
        product_url TEXT,
        scraped_at TEXT,
        imported_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_raw_grocery_products_batch
        ON raw_grocery_products(import_batch_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS mapped_grocery_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        raw_id INTEGER NOT NULL REFERENCES raw_grocery_products(id),
        source_name TEXT NOT NULL,
        source_product_id TEXT,
        title TEXT NOT NULL,
        brand TEXT,
        canonical_id TEXT,
        package_quantity REAL,
        package_unit TEXT,
        multipack_count REAL,
        normalized_total_quantity REAL,
        normalized_unit TEXT,
        current_price_aed REAL,
        normalized_price_per_unit REAL,
        category2 TEXT,
        product_type TEXT,
        mapping_status TEXT NOT NULL,
        rejection_reason TEXT,
        package_basis_source TEXT,
        product_url TEXT,
        scraped_at TEXT,
        imported_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_mapped_grocery_products_canonical
        ON mapped_grocery_products(canonical_id, normalized_unit)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_mapped_grocery_products_status
        ON mapped_grocery_products(mapping_status)
    """,
    """
    CREATE TABLE IF NOT EXISTS ingredient_prices (
        canonical_id TEXT NOT NULL,
        normalized_unit TEXT NOT NULL,
        display_name TEXT NOT NULL,
        normalized_price_per_unit REAL NOT NULL,
        package_quantity REAL,
        package_unit TEXT,
        package_price_aed REAL,
        normalized_package_quantity REAL,
        contributor_count INTEGER NOT NULL,
        aggregation_basis TEXT NOT NULL,
        source_name TEXT NOT NULL,
        source_product_name TEXT,
        source_url TEXT,
        collected_at TEXT NOT NULL,
        PRIMARY KEY (canonical_id, normalized_unit),
        CHECK (normalized_price_per_unit > 0),
        CHECK (contributor_count >= 1)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS manual_price_entries (
        canonical_id TEXT NOT NULL,
        normalized_unit TEXT NOT NULL,
        display_name TEXT NOT NULL,
        normalized_price_per_unit REAL NOT NULL,
        package_quantity REAL,
        package_unit TEXT,
        package_price_aed REAL,
        normalized_package_quantity REAL,
        source_type TEXT NOT NULL DEFAULT 'manual_curated',
        provenance_note TEXT NOT NULL,
        collected_at TEXT NOT NULL,
        PRIMARY KEY (canonical_id, normalized_unit),
        CHECK (normalized_price_per_unit > 0)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingredient_aliases (
        alias TEXT PRIMARY KEY,
        canonical_id TEXT NOT NULL,
        source TEXT NOT NULL,
        confidence REAL NOT NULL DEFAULT 1.0,
        CHECK (confidence >= 0.0 AND confidence <= 1.0)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_ingredient_aliases_canonical
        ON ingredient_aliases(canonical_id)
    """,
)


def create_schema(connection) -> None:
    for statement in SCHEMA_STATEMENTS:
        connection.execute(statement)
    connection.commit()
