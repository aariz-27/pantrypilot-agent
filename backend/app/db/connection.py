"""SQLite connection helper for the grocery pricing reference store.

Runtime read paths (PriceRepository) must never write; ingestion
scripts open their own read-write connections explicitly.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def connect(db_path: str | Path, *, read_only: bool = False) -> sqlite3.Connection:
    path = Path(db_path)
    if read_only:
        if not path.exists():
            raise FileNotFoundError(f"Reference price database not found: {path}")
        uri = f"file:{path}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def connection_scope(db_path: str | Path, *, read_only: bool = False) -> Iterator[sqlite3.Connection]:
    connection = connect(db_path, read_only=read_only)
    try:
        yield connection
    finally:
        connection.close()
