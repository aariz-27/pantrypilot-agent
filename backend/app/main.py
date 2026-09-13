from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.api.admin_audit import router as admin_audit_router
from app.api.admin_auth import router as admin_auth_router
from app.api.admin_dashboard import router as admin_dashboard_router
from app.api.admin_ingredients import router as admin_ingredients_router
from app.api.admin_prices import router as admin_prices_router
from app.api.health import router as health_router
from app.api.ingredients import router as ingredients_router
from app.api.recommend import router as recommend_router
from app.config import get_settings
from app.domain.errors import PantryPilotError
from app.logging_config import configure_logging
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.request_size_limit import RequestSizeLimitMiddleware
from app.rate_limit import limiter, rate_limit_exceeded_handler

# Per docs/API_INTEGRATION_STANDARDS.md section 11. Codes not listed
# here fall back to 500 -- an unrecognized failure is never assumed
# safe to expose as a more specific status.
_ERROR_CODE_HTTP_STATUS: dict[str, int] = {
    "INVALID_INPUT": 422,
    "RECIPE_PROVIDER_TIMEOUT": 503,
    "RECIPE_PROVIDER_UNAVAILABLE": 503,
    "RECIPE_PROVIDER_RATE_LIMITED": 503,
    "RECIPE_PROVIDER_MALFORMED_RESPONSE": 502,
    "RECIPE_PROVIDER_CONFIGURATION_ERROR": 503,
    "RECIPE_NOT_FOUND": 404,
    "LLM_PROVIDER_TIMEOUT": 503,
    "LLM_PROVIDER_UNAVAILABLE": 503,
    "LLM_PROVIDER_CONFIGURATION_ERROR": 503,
    "LLM_PROVIDER_MALFORMED_RESPONSE": 502,
    "AGENT_MALFORMED_ACTION": 503,
    "AGENT_UNSUPPORTED_ACTION": 500,
    "ADMIN_UNAUTHORIZED": 401,
    "ADMIN_CSRF_INVALID": 403,
    "ADMIN_NOT_FOUND": 404,
    "ADMIN_CONFLICT": 409,
    "ADMIN_VALIDATION_ERROR": 422,
    "ADMIN_NOT_CONFIGURED": 503,
}


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    # 2026-09-13 security hardening patch: /docs, /redoc, and
    # /openapi.json are public, unauthenticated, and expose the full
    # API surface (every route, schema, and parameter) -- disabled in
    # production only. FastAPI's own docs_url/redoc_url/openapi_url
    # kwargs already do this cleanly; no custom middleware needed.
    # development/test keep the existing (default) URLs unchanged.
    is_production = settings.environment == "production"
    app = FastAPI(
        title="PantryPilot API",
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
    )
    app.state.limiter = limiter

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Each middleware below is added after the previous one so it
    # becomes progressively more outermost (Starlette wraps the
    # most-recently-added user middleware outermost): request logging
    # wraps everything (captures true end-to-end latency/status),
    # oversized bodies are rejected next -- before any other
    # middleware or route/dependency code runs.
    app.add_middleware(RequestSizeLimitMiddleware, max_body_bytes=settings.max_request_body_bytes)
    app.add_middleware(RequestLoggingMiddleware)

    @app.exception_handler(PantryPilotError)
    async def pantrypilot_error_handler(request: Request, exc: PantryPilotError) -> JSONResponse:
        # Never leak exception internals/stack traces (docs/AGENTS.md
        # security section) -- exc.message is always a pre-written,
        # safe, controlled string on every PantryPilotError subclass.
        status_code = _ERROR_CODE_HTTP_STATUS.get(exc.code, 500)
        return JSONResponse(status_code=status_code, content=exc.to_error_envelope())

    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    app.include_router(health_router, prefix="/api")
    app.include_router(recommend_router, prefix="/api")
    app.include_router(ingredients_router, prefix="/api")
    # Admin dashboard (feature/admin-ingredient-dashboard, ticket
    # section 5): a separate /api/admin/... namespace. Every route in
    # these routers independently enforces its own session/CSRF
    # dependency (app.admin.deps) -- this include_router call adds no
    # additional auth of its own, matching the public routers' style.
    app.include_router(admin_auth_router, prefix="/api")
    app.include_router(admin_ingredients_router, prefix="/api")
    app.include_router(admin_prices_router, prefix="/api")
    app.include_router(admin_audit_router, prefix="/api")
    app.include_router(admin_dashboard_router, prefix="/api")
    return app


app = create_app()
