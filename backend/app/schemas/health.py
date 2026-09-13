from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    # 2026-09-13 security hardening patch: optional, defaulting to
    # None/omitted in production (app.api.health) so the public,
    # unauthenticated health check reveals no database or provider
    # configuration detail there. development/test still populate both
    # fields exactly as before -- unchanged, existing response shape.
    database: Literal["not_configured", "ok", "unavailable"] | None = None
    providers: dict[str, Literal["configured", "not_configured"]] | None = None
    build_version: str | None = None
