"""GET /api/health (TECHNICAL_SPEC.md section 15).

The grocery pricing reference database (M10/M14) shipped in PP-003 and
is now real, so `database` reflects an actual read-only reachability
check against `settings.price_db_path` (AC-25: "/api/health detects
database failure") rather than the pre-PP-003 static placeholder value.
"not_configured" remains a valid response-schema value (unchanged
public contract) but this endpoint no longer emits it, since
`price_db_path` always has a default and is never genuinely unset.

Only configuration presence/absence is reported for providers -- never
the secret values themselves.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.db.connection import check_database_health
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def get_health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        database="ok" if check_database_health(settings.price_db_path) else "unavailable",
        providers={
            "recipeapi_io": "configured" if settings.recipeapi_io_configured else "not_configured",
            "llm": "configured" if settings.llm_configured else "not_configured",
        },
        build_version=None,
    )
