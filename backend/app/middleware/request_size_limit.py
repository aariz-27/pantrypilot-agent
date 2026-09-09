"""Module F 4.2: deterministic max request-body size.

A raw ASGI middleware (not BaseHTTPMiddleware, which buffers the whole
body itself before any cap could apply) so oversized requests are
rejected while the body is still streaming in -- before Pydantic
validation, before any dependency, and before the recommend/agent path
ever runs. Content-Length is checked up front for a fast rejection
when present and honest; the same ceiling is independently enforced
against the actual bytes received while the body streams, so an
absent, malformed, or understated Content-Length (e.g. chunked
transfer-encoding) cannot bypass the cap.
"""

from __future__ import annotations

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_ERROR_ENVELOPE = json.dumps(
    {
        "request_id": None,
        "error": {
            "code": "REQUEST_TOO_LARGE",
            "message": "Request body exceeds the maximum allowed size.",
            "retryable": False,
        },
    }
).encode("utf-8")


class _PayloadTooLarge(Exception):
    pass


class RequestSizeLimitMiddleware:
    def __init__(self, app: ASGIApp, max_body_bytes: int) -> None:
        self._app = app
        self._max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                declared = None
            if declared is not None and declared > self._max_body_bytes:
                await _reject(send)
                return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self._max_body_bytes:
                    raise _PayloadTooLarge()
            return message

        try:
            await self._app(scope, limited_receive, send)
        except _PayloadTooLarge:
            await _reject(send)


async def _reject(send: Send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": _ERROR_ENVELOPE})
