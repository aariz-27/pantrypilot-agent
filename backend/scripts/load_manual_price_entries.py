#!/usr/bin/env python3
"""Load the small, reviewed manual/curated price fallback (DEC-013)
into manual_price_entries.

PP-003 does not pre-populate this file with any pricing data --
backend/data/manual/manual_price_entries.json ships empty. This
mechanism exists so that after reviewing the QA report
(scripts/grocery_qa_report.py), the Founder can add a small number of
hand-verified entries for important ingredients LuLu's export doesn't
usefully cover. PriceRepository checks this table as a fallback only
when no LuLu-derived reference exists for a canonical ID.

Every entry MUST have all of the following (enforced below -- an entry
missing any of them is rejected, never silently defaulted):

    {
      "canonical_id": "saffron",
      "normalized_unit": "g",
      "display_name": "Saffron",
      "normalized_price_per_unit": 0.45,
      "package_quantity": 1,
      "package_unit": "g",
      "package_price_aed": 0.45,
      "normalized_package_quantity": 1,
      "provenance_note": "Manually verified at <store>, <date>, by <person>."
    }

Usage:
    python scripts/load_manual_price_entries.py [--file backend/data/manual/manual_price_entries.json] [--db data/pantrypilot.db]
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

_REQUIRED_FIELDS = (
    "canonical_id",
    "normalized_unit",
    "display_name",
    "normalized_price_per_unit",
    "package_price_aed",
    "normalized_package_quantity",
    "provenance_note",
)


def load_manual_entries(entries_path: str, db_path: str) -> int:
    with open(entries_path, "r", encoding="utf-8") as f:
        entries = json.load(f)
    if not isinstance(entries, list):
        raise ValueError(f"Expected a JSON array in {entries_path}")

    collected_at = datetime.now(timezone.utc).date().isoformat()
    rows = []
    for entry in entries:
        missing = [field for field in _REQUIRED_FIELDS if not entry.get(field)]
        if missing:
            raise ValueError(f"Manual entry {entry!r} is missing required fields: {missing}")
        if entry["normalized_price_per_unit"] <= 0 or entry["package_price_aed"] <= 0:
            raise ValueError(f"Manual entry {entry!r} has a non-positive price -- rejected")
        rows.append(
            (
                entry["canonical_id"],
                entry["normalized_unit"],
                entry["display_name"],
                entry["normalized_price_per_unit"],
                entry.get("package_quantity"),
                entry.get("package_unit"),
                entry["package_price_aed"],
                entry["normalized_package_quantity"],
                "manual_curated",
                entry["provenance_note"],
                collected_at,
            )
        )

    with connection_scope(db_path, read_only=False) as connection:
        create_schema(connection)
        connection.execute("DELETE FROM manual_price_entries")
        connection.executemany(
            """
            INSERT INTO manual_price_entries (
                canonical_id, normalized_unit, display_name, normalized_price_per_unit,
                package_quantity, package_unit, package_price_aed, normalized_package_quantity,
                source_type, provenance_note, collected_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        connection.commit()

    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default="data/manual/manual_price_entries.json")
    parser.add_argument("--db", default="data/pantrypilot.db")
    args = parser.parse_args()
    count = load_manual_entries(args.file, args.db)
    print(f"Loaded {count} manual price entries into {args.db}")


if __name__ == "__main__":
    main()
