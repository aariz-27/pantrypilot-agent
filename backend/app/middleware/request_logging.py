"""Module F 4.7: minimal structured request logging.

Logs only non-sensitive, high-level fields: a per-request id (log
correlation only -- distinct from the AgentRequest.request_id minted
inside app.api.recommend), method, path, status code, latency, and a
coarse failure category. Never logs headers, query strings, request
bodies, or provider URLs/credentials.

Query strings are deliberately excluded even though the only current
one (GET /api/ingredients/suggest?q=...) is just user-typed search
text and low-sensitivity on its own -- excluding it means no request
text of any kind reaches the logs, and this is meant to be the ONLY
http-level access log PantryPilot produces: run uvicorn with
--no-access-log (or an equivalent log_config disabling its access
logger) in production so uvicorn's own default access log, which DOES
include the full request line/query string, isn't also written
alongside this one.
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("pantrypilot.access")


def _failure_category(status_code: int) -> str | None:
    if status_code < 400:
        return None
    if status_code == 422:
        return "validation_error"
    if status_code == 413:
        return "request_too_large"
    if status_code == 429:
        return "rate_limited"
    if status_code in (502, 503):
        return "upstream_failure"
    if status_code >= 500:
        return "internal_error"
    return "client_error"


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request_id = f"req_{uuid.uuid4().hex}"
        started_at = time.monotonic()
        status_code = 500  # only overwritten below if a response actually starts

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self._app(scope, receive, send_wrapper)
        finally:
            latency_ms = (time.monotonic() - started_at) * 1000
            category = _failure_category(status_code)
            logger.info(
                "request_id=%s method=%s path=%s status=%d latency_ms=%.1f failure_category=%s",
                request_id,
                scope.get("method", ""),
                scope.get("path", ""),
                status_code,
                latency_ms,
                category or "-",
            )
