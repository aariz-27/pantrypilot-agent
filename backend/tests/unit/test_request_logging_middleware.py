"""Module F 4.7: RequestLoggingMiddleware emits safe, structured
access-log lines and never includes the query string (so no request
text, e.g. an autocomplete search term, ever reaches the logs)."""

from __future__ import annotations

import logging

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.middleware.request_logging import RequestLoggingMiddleware, _failure_category


async def _ok(request):
    return PlainTextResponse("ok")


def _client() -> TestClient:
    app = Starlette(routes=[Route("/greet", _ok, methods=["GET"])])
    app.add_middleware(RequestLoggingMiddleware)
    return TestClient(app)


def test_logs_method_path_status_and_latency_without_the_query_string(caplog):
    with caplog.at_level(logging.INFO, logger="pantrypilot.access"):
        response = _client().get("/greet", params={"secret_looking_param": "should-not-be-logged"})
    assert response.status_code == 200
    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert "method=GET" in message
    assert "path=/greet" in message
    assert "status=200" in message
    assert "latency_ms=" in message
    assert "secret_looking_param" not in message
    assert "should-not-be-logged" not in message


def test_failure_category_buckets_status_codes_sensibly():
    assert _failure_category(200) is None
    assert _failure_category(422) == "validation_error"
    assert _failure_category(413) == "request_too_large"
    assert _failure_category(429) == "rate_limited"
    assert _failure_category(503) == "upstream_failure"
    assert _failure_category(500) == "internal_error"
    assert _failure_category(404) == "client_error"
