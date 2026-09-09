"""Module F 4.2: RequestSizeLimitMiddleware boundary behavior.

Exercises the middleware directly against a minimal Starlette app (not
the full PantryPilot app) so the exact boundary byte count is
controlled precisely, independent of RecommendRequest's own schema
bounds. tests/integration/test_request_size_limit_endpoint.py covers
the real /api/recommend endpoint end to end.
"""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.middleware.request_size_limit import RequestSizeLimitMiddleware

_MAX_BYTES = 100


async def _echo(request: Request) -> JSONResponse:
    body = await request.body()
    return JSONResponse({"received_bytes": len(body)})


def _client() -> TestClient:
    app = Starlette(routes=[Route("/echo", _echo, methods=["POST"])])
    app.add_middleware(RequestSizeLimitMiddleware, max_body_bytes=_MAX_BYTES)
    return TestClient(app)


def test_body_at_the_limit_passes_through_to_the_handler():
    response = _client().post("/echo", content=b"x" * _MAX_BYTES)
    assert response.status_code == 200
    assert response.json()["received_bytes"] == _MAX_BYTES


def test_body_over_the_limit_is_rejected_with_a_controlled_413():
    response = _client().post("/echo", content=b"x" * (_MAX_BYTES + 1))
    assert response.status_code == 413
    envelope = response.json()
    assert envelope["error"]["code"] == "REQUEST_TOO_LARGE"
    assert envelope["error"]["retryable"] is False
    # No traceback/internal detail -- just the fixed, safe envelope.
    assert set(envelope["error"].keys()) == {"code", "message", "retryable"}
