"""Module F 4.3: lightweight, production-suitable rate limiting.

Uses slowapi's default in-memory storage -- no Redis or other
distributed system. This is a deliberate, documented limitation for
the competition deployment (single Oracle Cloud VM, one process): the
counters reset on process restart and are not shared across multiple
worker processes/instances. If PantryPilot is ever scaled to more than
one process, this needs a shared backend (e.g. slowapi's Redis storage
option) to remain effective -- see docs/MODULE_F_SECURITY_REPORT.md.

On a rejected request, the exception handler below returns the same
{request_id, error: {code, message, retryable}} envelope shape as
app.domain.errors.PantryPilotError.to_error_envelope(), so the
frontend's existing generic error-handling path needs no special case
beyond checking the HTTP status code.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    response = JSONResponse(
        status_code=429,
        content={
            "request_id": None,
            "error": {
                "code": "RATE_LIMITED",
                "message": "Too many requests. Please wait a moment and try again.",
                "retryable": True,
            },
        },
    )
    response.headers["Retry-After"] = "60"
    return response
