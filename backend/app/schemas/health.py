from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["not_configured", "ok", "unavailable"]
    providers: dict[str, Literal["configured", "not_configured"]]
    build_version: str | None = None
