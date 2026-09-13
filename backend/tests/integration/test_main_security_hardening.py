"""2026-09-13 security hardening patch: FastAPI's own docs_url/
redoc_url/openapi_url are disabled in production only.

app.main.app is built once at import time via create_app(), which
reads settings via get_settings() as plain module-level code -- not a
FastAPI Depends() -- so app.dependency_overrides cannot influence it.
These tests instead monkeypatch app.main.get_settings itself and call
create_app() directly to get a fresh app instance for each environment,
leaving the shared app.main.app instance used by every other test
file untouched.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as main_module
from app.config import Settings


def _fresh_app(monkeypatch, environment: str):
    monkeypatch.setattr(main_module, "get_settings", lambda: Settings(_env_file=None, environment=environment))
    return main_module.create_app()


def test_production_disables_docs_redoc_and_openapi(monkeypatch):
    client = TestClient(_fresh_app(monkeypatch, "production"))
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_development_keeps_docs_redoc_and_openapi_available(monkeypatch):
    client = TestClient(_fresh_app(monkeypatch, "development"))
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_test_environment_keeps_docs_available(monkeypatch):
    # "test" is treated the same as "development" -- only "production"
    # disables the docs surface.
    client = TestClient(_fresh_app(monkeypatch, "test"))
    assert client.get("/docs").status_code == 200
