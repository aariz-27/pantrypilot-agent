#!/usr/bin/env python3
"""Deterministic raw -> mapped -> reference pipeline (M14 layer 2/M10
layer 3). Idempotent: safe to re-run after taxonomy/parsing rule
changes without re-importing raw data.

Usage:
    python scripts/normalize_grocery_prices.py [--db data/pantrypilot.db]
"""

from __future__ import annotations

import argparse
import collections
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.connection import connection_scope  # noqa: E402
from app.db.schema import create_schema  # noqa: E402
from app.domain.grocery_filtering import is_relevant_product  # noqa: E402
from app.domain.grocery_models import MappingStatus, ReferencePriceCandidate  # noqa: E402
from app.domain.grocery_parsing import (  # noqa: E402
    clean_brand,
    parse_package_content,
    parse_price,
    resolve_canonical_id,
    validate_currency,
)
from app.domain.reference_pricing import compute_reference_prices  # noqa: E402


def _mapped_row(
    raw_row,
    status: MappingStatus,
    rejection_reason: str | None,
    *,
    price: float | None = None,
    canonical_id: str | None = None,
    parsed=None,
    normalized_price_per_unit: float | None = None,
    imported_at: str,
) -> dict:
    return {
        "raw_id": raw_row["id"],
        "source_name": raw_row["source_name"],
        "source_product_id": raw_row["source_product_id"] or raw_row["sku"],
        "title": raw_row["title"],
        "brand": clean_brand(raw_row["brand"]),
        "canonical_id": canonical_id,
        "package_quantity": parsed.package_quantity if parsed else None,
        "package_unit": parsed.package_unit if parsed else None,
        "multipack_count": parsed.multipack_count if parsed else None,
        "normalized_total_quantity": parsed.normalized_total_quantity if parsed else None,
        "normalized_unit": parsed.normalized_unit if parsed else None,
        "current_price_aed": price,
        "normalized_price_per_unit": normalized_price_per_unit,
        "category2": raw_row["category2"],
        "product_type": raw_row["product_type"],
        "mapping_status": status.value,
        "rejection_reason": rejection_reason,
        "package_basis_source": parsed.basis_source.value if parsed and parsed.basis_source else None,
        "product_url": raw_row["product_url"],
        "scraped_at": raw_row["scraped_at"],
        "imported_at": imported_at,
    }


def run_normalization(db_path: str) -> dict:
    stats: collections.Counter = collections.Counter()
    imported_at = datetime.now(timezone.utc).isoformat()

    with connection_scope(db_path, read_only=False) as connection:
        create_schema(connection)
        connection.execute("DELETE FROM mapped_grocery_products")
        connection.execute("DELETE FROM ingredient_prices")
        connection.commit()

        raw_rows = connection.execute("SELECT * FROM raw_grocery_products").fetchall()
        stats["raw_total"] = len(raw_rows)

        seen_keys: set[tuple[str, str]] = set()
        mapped_rows: list[dict] = []

        for row in raw_rows:
            dedupe_key = (row["source_name"], row["source_product_id"] or row["sku"] or row["title"])
            if dedupe_key in seen_keys:
                mapped_rows.append(
                    _mapped_row(row, MappingStatus.DUPLICATE, "duplicate source_product_id/sku", imported_at=imported_at)
                )
                stats["duplicate"] += 1
                continue
            seen_keys.add(dedupe_key)

            if not is_relevant_product(row["category2"], row["product_type"]):
                mapped_rows.append(
                    _mapped_row(
                        row, MappingStatus.FILTERED_OUT,
                        "not an approved ingredient category/productType", imported_at=imported_at,
                    )
                )
                stats["filtered_out"] += 1
                continue

            if not validate_currency(row["currency_raw"]):
                mapped_rows.append(
                    _mapped_row(
                        row, MappingStatus.INVALID_CURRENCY,
                        f"unexpected currency: {row['currency_raw']!r}", imported_at=imported_at,
                    )
                )
                stats["invalid_currency"] += 1
                continue

            price = parse_price(row["price_raw"])
            if price is None:
                mapped_rows.append(
                    _mapped_row(
                        row, MappingStatus.UNPARSEABLE_PRICE,
                        f"unparseable/non-positive price: {row['price_raw']!r}", imported_at=imported_at,
                    )
                )
                stats["unparseable_price"] += 1
                continue

            canonical_id = resolve_canonical_id(row["product_type"], row["title"])
            if canonical_id is None:
                mapped_rows.append(
                    _mapped_row(
                        row, MappingStatus.UNMAPPED_INGREDIENT, "no canonical mapping rule matched",
                        price=price, imported_at=imported_at,
                    )
                )
                stats["unmapped_ingredient"] += 1
                continue

            parsed = parse_package_content(row["content"])

            if parsed.unsupported_unit_token is not None:
                mapped_rows.append(
                    _mapped_row(
                        row, MappingStatus.UNSUPPORTED_UNIT,
                        f"unsupported unit: {parsed.unsupported_unit_token}",
                        price=price, canonical_id=canonical_id, parsed=parsed, imported_at=imported_at,
                    )
                )
                stats["unsupported_unit"] += 1
                continue

            if parsed.normalized_unit is None or not parsed.normalized_total_quantity:
                mapped_rows.append(
                    _mapped_row(
                        row, MappingStatus.UNPARSEABLE_PACKAGE,
                        f"unparseable content: {row['content']!r}",
                        price=price, canonical_id=canonical_id, imported_at=imported_at,
                    )
                )
                stats["unparseable_package"] += 1
                continue

            normalized_price_per_unit = round(price / parsed.normalized_total_quantity, 6)
            mapped_rows.append(
                _mapped_row(
                    row, MappingStatus.MAPPED, None,
                    price=price, canonical_id=canonical_id, parsed=parsed,
                    normalized_price_per_unit=normalized_price_per_unit, imported_at=imported_at,
                )
            )
            stats["mapped"] += 1

        connection.executemany(
            """
            INSERT INTO mapped_grocery_products (
                raw_id, source_name, source_product_id, title, brand, canonical_id,
                package_quantity, package_unit, multipack_count, normalized_total_quantity,
                normalized_unit, current_price_aed, normalized_price_per_unit, category2,
                product_type, mapping_status, rejection_reason, package_basis_source,
                product_url, scraped_at, imported_at
            ) VALUES (:raw_id, :source_name, :source_product_id, :title, :brand, :canonical_id,
                :package_quantity, :package_unit, :multipack_count, :normalized_total_quantity,
                :normalized_unit, :current_price_aed, :normalized_price_per_unit, :category2,
                :product_type, :mapping_status, :rejection_reason, :package_basis_source,
                :product_url, :scraped_at, :imported_at)
            """,
            mapped_rows,
        )
        connection.commit()

        mapped_ok = [r for r in mapped_rows if r["mapping_status"] == MappingStatus.MAPPED.value]
        grouped: dict[tuple[str, str], list[ReferencePriceCandidate]] = collections.defaultdict(list)
        for r in mapped_ok:
            grouped[(r["canonical_id"], r["normalized_unit"])].append(
                ReferencePriceCandidate(
                    normalized_price_per_unit=r["normalized_price_per_unit"],
                    package_quantity=r["package_quantity"],
                    package_unit=r["package_unit"],
                    package_price_aed=r["current_price_aed"],
                    normalized_package_quantity=r["normalized_total_quantity"],
                    source_product_name=r["title"],
                    source_name=r["source_name"],
                    source_url=r["product_url"],
                )
            )

        results, incompatible = compute_reference_prices(dict(grouped))
        stats["incompatible_unit_groups"] = len(incompatible)
        stats["promoted_reference_entries"] = len(results)
        stats["canonical_ingredient_count"] = len({r.canonical_id for r in results})

        collected_at = datetime.now(timezone.utc).date().isoformat()
        connection.executemany(
            """
            INSERT INTO ingredient_prices (
                canonical_id, normalized_unit, display_name, normalized_price_per_unit,
                package_quantity, package_unit, package_price_aed, normalized_package_quantity,
                contributor_count, aggregation_basis, source_name, source_product_name,
                source_url, collected_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    r.canonical_id,
                    r.normalized_unit,
                    r.canonical_id.replace("_", " "),
                    r.normalized_price_per_unit,
                    r.package_quantity,
                    r.package_unit,
                    r.package_price_aed,
                    r.normalized_package_quantity,
                    r.contributor_count,
                    r.aggregation_basis,
                    r.source_name,
                    r.source_product_name,
                    r.source_url,
                    collected_at,
                )
                for r in results
            ],
        )
        connection.commit()

    return dict(stats)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/pantrypilot.db", help="SQLite DB path")
    args = parser.parse_args()

    stats = run_normalization(args.db)
    for key, value in sorted(stats.items()):
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
