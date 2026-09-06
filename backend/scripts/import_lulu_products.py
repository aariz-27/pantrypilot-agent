#!/usr/bin/env python3
"""Import a LuLu UAE grocery export (Apify actor output) into the raw
staging table only (M14, layer 1: verbatim, no parsing/mapping/pricing).

Usage:
    python scripts/import_lulu_products.py <path-to-json> [--db data/pantrypilot.db]

Tolerates nullable/nonessential fields -- only `title` is required to
exist (falls back to an empty string, which will simply fail later
mapping steps rather than crash ingestion). Never calls Apify or any
network resource; reads a local JSON file only.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.connection import connection_scope  # noqa: E402
from app.db.schema import create_schema  # noqa: E402


def _num(record: dict, key: str) -> float | None:
    value = record.get(key)
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _str(record: dict, key: str) -> str | None:
    value = record.get(key)
    if value is None:
        return None
    return str(value)


def import_products(json_path: str, db_path: str, source_name: str = "lulu_uae") -> tuple[str, int]:
    with open(json_path, "r", encoding="utf-8") as f:
        records = json.load(f)
    if not isinstance(records, list):
        raise ValueError(f"Expected a JSON array of products in {json_path}")

    batch_id = f"{source_name}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    imported_at = datetime.now(timezone.utc).isoformat()

    rows = []
    for record in records:
        if not isinstance(record, dict):
            continue
        in_stock_raw = record.get("inStock")
        in_stock = 1 if in_stock_raw is True else (0 if in_stock_raw is False else None)
        rows.append(
            (
                batch_id,
                source_name,
                _str(record, "id"),
                _str(record, "sku"),
                record.get("title") or "",
                _str(record, "brand"),
                _str(record, "content"),
                _num(record, "price"),
                _num(record, "retailPrice"),
                _num(record, "discountAmount"),
                _num(record, "discountRatio"),
                _str(record, "currency"),
                _str(record, "category1"),
                _str(record, "category2"),
                _str(record, "category3"),
                _str(record, "productType"),
                in_stock,
                _str(record, "url"),
                _str(record, "scrapedAt"),
                imported_at,
            )
        )

    with connection_scope(db_path, read_only=False) as connection:
        create_schema(connection)
        connection.executemany(
            """
            INSERT INTO raw_grocery_products (
                import_batch_id, source_name, source_product_id, sku, title, brand,
                content, price_raw, retail_price_raw, discount_amount_raw, discount_ratio_raw,
                currency_raw, category1, category2, category3, product_type, in_stock,
                product_url, scraped_at, imported_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        connection.commit()

    return batch_id, len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_path", help="Path to the LuLu export JSON file")
    parser.add_argument("--db", default="data/pantrypilot.db", help="SQLite DB path")
    args = parser.parse_args()

    batch_id, count = import_products(args.json_path, args.db)
    print(f"Imported {count} raw records into {args.db} (batch_id={batch_id})")


if __name__ == "__main__":
    main()
