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

2026-09-13 security hardening patch: in production, `database` and
`providers` are omitted entirely (this public, unauthenticated
endpoint returns only `{"status": "ok"}`) so no configuration/
integration state is exposed to an unauthenticated caller.
development/test are unaffected.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.db.connection import check_database_health
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def get_health(settings: Settings = Depends(get_settings)) -> HealthResponse | JSONResponse:
    # 2026-09-13 security hardening patch: this endpoint is public and
    # unauthenticated. In production it reveals nothing beyond basic
    # liveness -- no database reachability detail, no RecipeAPI/LLM
    # configuration state (an attacker could otherwise fingerprint
    # which integrations are live). development/test keep the existing
    # detailed response unchanged, preserving current tests/tooling.
    #
    # 2026-09-13 correction (architect review): a HealthResponse(status="ok")
    # still serializes database/providers/build_version as explicit
    # JSON nulls under response_model=HealthResponse -- those keys must
    # not exist in the production body at all. Returning a JSONResponse
    # directly bypasses response_model serialization entirely (FastAPI
    # passes an already-a-Response return value straight through), so
    # the production body is exactly {"status": "ok"}, nothing else.
    if settings.environment == "production":
        return JSONResponse(content={"status": "ok"})
    return HealthResponse(
        status="ok",
        database="ok" if check_database_health(settings.price_db_path) else "unavailable",
        providers={
            "recipeapi_io": "configured" if settings.recipeapi_io_configured else "not_configured",
            "llm": "configured" if settings.llm_configured else "not_configured",
        },
        build_version=None,
    )
