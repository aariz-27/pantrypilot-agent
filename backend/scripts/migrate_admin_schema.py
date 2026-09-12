#!/usr/bin/env python3
"""One-time (repeatable) migration: add the admin dashboard tables/
columns to the existing pricing reference database (ticket section 32).

Idempotent and additive only -- see app.db.admin_schema's module
docstring. Safe to run against a production database that already has
the base PP-003 schema; safe to run more than once. Never drops,
renames, or rewrites any existing row.

Usage:
    python scripts/migrate_admin_schema.py [--db data/pantrypilot.db]

Always back up the database file first in production -- see
docs/admin/ADMIN_DASHBOARD.md "Database backup" for the exact command.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.admin_schema import create_admin_schema  # noqa: E402
from app.db.connection import connection_scope  # noqa: E402
from app.db.schema import create_schema  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/pantrypilot.db", help="Path to the SQLite database file")
    args = parser.parse_args()

    with connection_scope(args.db, read_only=False) as connection:
        # Safe even if the base schema is already present -- every
        # statement in both create_schema and create_admin_schema is
        # CREATE TABLE/INDEX IF NOT EXISTS or a guarded ALTER TABLE.
        create_schema(connection)
        create_admin_schema(connection)

    print(f"Admin schema migration applied to {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
