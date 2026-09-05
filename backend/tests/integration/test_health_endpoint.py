from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app


def test_health_returns_200_and_expected_shape():
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    try:
        client = TestClient(app)
        response = client.get("/api/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["database"] == "not_configured"
        assert body["providers"] == {"recipeapi_io": "not_configured", "llm": "not_configured"}
    finally:
        app.dependency_overrides.clear()


def test_health_reports_configured_providers_without_leaking_secrets():
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        anthropic_api_key="sk-secret-value",
        pantrypilot_llm_model="claude-sonnet-5",
        recipeapi_io_api_key="rk-secret-value",
    )
    try:
        client = TestClient(app)
        response = client.get("/api/health")
        body = response.json()
        assert body["providers"] == {"recipeapi_io": "configured", "llm": "configured"}
        assert "sk-secret-value" not in response.text
        assert "rk-secret-value" not in response.text
    finally:
        app.dependency_overrides.clear()
