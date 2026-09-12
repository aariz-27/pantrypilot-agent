"""Admin session persistence (feature/admin-ingredient-dashboard).

A server-side session row is the source of truth for whether a signed
session cookie is still valid -- this is what makes explicit logout and
expiry real (a bare signed cookie alone could never be revoked before
its expiry). Opens its own connection per call, same low-QPS pattern
PriceRepository already uses; admin traffic is operator-only, not a hot
path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.db.connection import connection_scope


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class AdminSessionRecord:
    session_id: str
    admin_username: str
    csrf_token: str
    created_at: str
    expires_at: str
    revoked_at: str | None


class AdminSessionRepository:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    def create_session(self, session_id: str, admin_username: str, csrf_token: str, ttl_minutes: int) -> AdminSessionRecord:
        created_at = _now_iso()
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)).isoformat().replace("+00:00", "Z")
        with connection_scope(self._db_path, read_only=False) as connection:
            connection.execute(
                """
                INSERT INTO admin_sessions (session_id, admin_username, csrf_token, created_at, expires_at, revoked_at)
                VALUES (?, ?, ?, ?, ?, NULL)
                """,
                (session_id, admin_username, csrf_token, created_at, expires_at),
            )
            connection.commit()
        return AdminSessionRecord(session_id, admin_username, csrf_token, created_at, expires_at, None)

    def get_active_session(self, session_id: str) -> AdminSessionRecord | None:
        """Returns None for a missing, revoked, OR expired session --
        callers never need to separately re-check expiry/revocation
        after this returns a record."""

        with connection_scope(self._db_path, read_only=False) as connection:
            row = connection.execute(
                "SELECT * FROM admin_sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            if row is None:
                return None
            if row["revoked_at"] is not None:
                return None
            if row["expires_at"] <= _now_iso():
                return None
            return AdminSessionRecord(
                session_id=row["session_id"],
                admin_username=row["admin_username"],
                csrf_token=row["csrf_token"],
                created_at=row["created_at"],
                expires_at=row["expires_at"],
                revoked_at=row["revoked_at"],
            )

    def revoke_session(self, session_id: str) -> None:
        with connection_scope(self._db_path, read_only=False) as connection:
            connection.execute(
                "UPDATE admin_sessions SET revoked_at = ? WHERE session_id = ? AND revoked_at IS NULL",
                (_now_iso(), session_id),
            )
            connection.commit()
