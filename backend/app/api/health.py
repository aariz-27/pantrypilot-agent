"""GET /api/health (TECHNICAL_SPEC.md section 15).

This foundation ticket does not implement the SQLite reference database
(M10/M14 are out of scope), so `database` is reported honestly as
"not_configured" rather than fabricating a healthy/unhealthy claim about
a dependency that does not exist yet. Detecting real database failure
(acceptance criterion 25) is deferred until the price repository lands.

Only configuration presence/absence is reported for providers -- never
the secret values themselves.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def get_health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        database="not_configured",
        providers={
            "recipeapi_io": "configured" if settings.recipeapi_io_configured else "not_configured",
            "llm": "configured" if settings.llm_configured else "not_configured",
        },
        build_version=None,
    )
