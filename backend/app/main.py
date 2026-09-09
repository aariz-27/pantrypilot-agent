from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

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
}


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(title="PantryPilot API")
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
    return app


app = create_app()
