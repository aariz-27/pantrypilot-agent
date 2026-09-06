#!/usr/bin/env python3
"""QA report for the grocery ingestion pipeline (M14/M10).

Reports exactly the statistics PP-003 requires so the Founder can
decide whether manual gap-fill (DEC-013's small curated fallback) is
necessary. Read-only against the already-populated database -- run
import_lulu_products.py and normalize_grocery_prices.py first.

Usage:
    python scripts/grocery_qa_report.py [--db data/pantrypilot.db]
"""

from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.connection import connection_scope  # noqa: E402
from app.domain.grocery_taxonomy import REFERENCE_PRICE_EXCLUDED_UNITS  # noqa: E402

# Common recipe staples worth specifically calling out if pricing
# coverage is missing -- not exhaustive, just a sanity spot-check list
# spanning the categories PantryPilot recipes most often need.
IMPORTANT_INGREDIENTS = [
    "onion", "garlic", "tomato", "potato", "egg", "full_fat_milk",
    "butter", "olive_oil", "sunflower_oil", "basmati_rice", "plain_flour",
    "whole_wheat_flour", "white_sugar", "salt", "black_pepper", "turmeric",
    "cumin", "chili_powder", "boneless_chicken_breast", "chicken_thigh",
    "whole_chicken", "minced_beef", "beef_steak", "lamb_chops",
    "plain_yoghurt", "cheddar_cheese", "feta_cheese", "bell_pepper",
    "cucumber", "spinach", "lentils", "chickpeas", "coriander", "ginger",
]


def build_report(db_path: str) -> str:
    lines: list[str] = []

    with connection_scope(db_path, read_only=True) as connection:
        raw_total = connection.execute("SELECT COUNT(*) AS c FROM raw_grocery_products").fetchone()["c"]

        status_counts = collections.Counter(
            {
                row["mapping_status"]: row["c"]
                for row in connection.execute(
                    "SELECT mapping_status, COUNT(*) AS c FROM mapped_grocery_products GROUP BY mapping_status"
                )
            }
        )

        promoted = connection.execute("SELECT COUNT(*) AS c FROM ingredient_prices").fetchone()["c"]
        canonical_count = connection.execute(
            "SELECT COUNT(DISTINCT canonical_id) AS c FROM ingredient_prices"
        ).fetchone()["c"]

        unit_distribution = collections.Counter(
            {
                row["normalized_unit"]: row["c"]
                for row in connection.execute(
                    "SELECT normalized_unit, COUNT(*) AS c FROM ingredient_prices GROUP BY normalized_unit"
                )
            }
        )

        unsupported_unit_tokens = collections.Counter(
            {
                row["rejection_reason"]: row["c"]
                for row in connection.execute(
                    """
                    SELECT rejection_reason, COUNT(*) AS c FROM mapped_grocery_products
                    WHERE mapping_status = 'unsupported_unit' GROUP BY rejection_reason
                    """
                )
            }
        )

        # Mirrors scripts/normalize_grocery_prices.py's own reference-price
        # candidate grouping exactly, including REFERENCE_PRICE_EXCLUDED_UNITS
        # (essential-ingredient data-quality fix, 2026-09-06): a canonical_id
        # with a real but categorically-incompatible unit contributor (e.g.
        # "butter"/ml for a roasting spray, "apple"/pcs for a piece-counted
        # pack) must not still be reported as an unresolved incompatible
        # group here once that contributor is excluded from promotion.
        unit_rows = connection.execute(
            "SELECT canonical_id, normalized_unit, COUNT(*) AS c FROM mapped_grocery_products "
            "WHERE mapping_status = 'mapped' GROUP BY canonical_id, normalized_unit"
        ).fetchall()
        units_by_canonical: dict[str, set[str]] = collections.defaultdict(set)
        counts_by_canonical_unit: dict[tuple[str, str], int] = {}
        for row in unit_rows:
            canonical_id, unit, count = row["canonical_id"], row["normalized_unit"], row["c"]
            counts_by_canonical_unit[(canonical_id, unit)] = count
            if unit in REFERENCE_PRICE_EXCLUDED_UNITS.get(canonical_id, frozenset()):
                continue
            units_by_canonical[canonical_id].add(unit)

        incompatible_rows = [
            {
                "canonical_id": canonical_id,
                "units": ",".join(sorted(units)),
                "c": sum(counts_by_canonical_unit[(canonical_id, u)] for u in units),
            }
            for canonical_id, units in sorted(units_by_canonical.items())
            if len(units) > 1
        ]

        missing_important = []
        for canonical_id in IMPORTANT_INGREDIENTS:
            found = connection.execute(
                "SELECT 1 FROM ingredient_prices WHERE canonical_id = ? LIMIT 1", (canonical_id,)
            ).fetchone()
            if not found:
                missing_important.append(canonical_id)

    lines.append("=== Grocery Ingestion QA Report ===")
    lines.append(f"raw_imported_count: {raw_total}")
    lines.append(f"mapped_count (status=mapped): {status_counts.get('mapped', 0)}")
    lines.append(f"unresolved_count (status=unmapped_ingredient): {status_counts.get('unmapped_ingredient', 0)}")
    lines.append(
        "rejected/filtered_count (filtered_out + invalid_currency + unparseable_price + "
        f"unparseable_package + unsupported_unit + duplicate): "
        f"{sum(status_counts[k] for k in ('filtered_out', 'invalid_currency', 'unparseable_price', 'unparseable_package', 'unsupported_unit', 'duplicate') if k in status_counts)}"
    )
    lines.append(f"  filtered_out: {status_counts.get('filtered_out', 0)}")
    lines.append(f"  invalid_currency: {status_counts.get('invalid_currency', 0)}")
    lines.append(f"  unparseable_price (missing/invalid price): {status_counts.get('unparseable_price', 0)}")
    lines.append(f"  unparseable_package: {status_counts.get('unparseable_package', 0)}")
    lines.append(f"  unsupported_unit: {status_counts.get('unsupported_unit', 0)}")
    lines.append(f"  duplicates: {status_counts.get('duplicate', 0)}")
    lines.append(f"promoted_reference_entries: {promoted}")
    lines.append(f"canonical_ingredient_count: {canonical_count}")
    lines.append(f"unit_distribution (promoted references): {dict(unit_distribution)}")
    lines.append(f"unsupported_unit_token_breakdown: {dict(unsupported_unit_tokens)}")
    lines.append(f"incompatible_unit_groups: {len(incompatible_rows)}")
    for row in incompatible_rows:
        lines.append(f"  - {row['canonical_id']}: units={row['units']} contributors={row['c']}")
    lines.append(f"important_ingredients_missing_price ({len(missing_important)}): {missing_important}")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/pantrypilot.db", help="SQLite DB path")
    args = parser.parse_args()
    print(build_report(args.db))


if __name__ == "__main__":
    main()
