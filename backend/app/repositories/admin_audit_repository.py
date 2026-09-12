"""Append-only admin audit log (ticket section 17).

Never records passwords, session secrets, authentication tokens, or
API keys -- callers pass only a pre-built `summary` string, and every
call site in app.api.admin_* is responsible for keeping that string to
safe, already-validated field values (never a raw request body dump).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.db.connection import connection_scope


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class AdminAuditEntry:
    id: int
    occurred_at: str
    admin_username: str
    action: str
    entity_type: str
    entity_id: str
    summary: str
    request_id: str | None


class AdminAuditRepository:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    def record(
        self,
        *,
        admin_username: str,
        action: str,
        entity_type: str,
        entity_id: str,
        summary: str,
        request_id: str | None = None,
    ) -> None:
        with connection_scope(self._db_path, read_only=False) as connection:
            connection.execute(
                """
                INSERT INTO admin_audit_log
                    (occurred_at, admin_username, action, entity_type, entity_id, summary, request_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (_now_iso(), admin_username, action, entity_type, entity_id, summary, request_id),
            )
            connection.commit()

    def list_entries(
        self, *, entity_type: str | None = None, page: int = 1, page_size: int = 25
    ) -> tuple[list[AdminAuditEntry], int]:
        bounded_page = max(1, page)
        bounded_page_size = max(1, min(page_size, 100))
        offset = (bounded_page - 1) * bounded_page_size

        with connection_scope(self._db_path, read_only=False) as connection:
            if entity_type is not None:
                total = connection.execute(
                    "SELECT COUNT(*) AS c FROM admin_audit_log WHERE entity_type = ?", (entity_type,)
                ).fetchone()["c"]
                rows = connection.execute(
                    """
                    SELECT * FROM admin_audit_log WHERE entity_type = ?
                    ORDER BY id DESC LIMIT ? OFFSET ?
                    """,
                    (entity_type, bounded_page_size, offset),
                ).fetchall()
            else:
                total = connection.execute("SELECT COUNT(*) AS c FROM admin_audit_log").fetchone()["c"]
                rows = connection.execute(
                    "SELECT * FROM admin_audit_log ORDER BY id DESC LIMIT ? OFFSET ?",
                    (bounded_page_size, offset),
                ).fetchall()

        entries = [
            AdminAuditEntry(
                id=row["id"],
                occurred_at=row["occurred_at"],
                admin_username=row["admin_username"],
                action=row["action"],
                entity_type=row["entity_type"],
                entity_id=row["entity_id"],
                summary=row["summary"],
                request_id=row["request_id"],
            )
            for row in rows
        ]
        return entries, total
