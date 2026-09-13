from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.db.connection import connection_scope
from app.db.schema import create_schema
from app.main import app


def test_health_returns_200_and_reports_database_unavailable_when_missing(tmp_path):
    # Audit finding (2026-09-07): the health endpoint used to hardcode
    # database="not_configured" even after PP-003 shipped a real SQLite
    # reference database, silently failing AC-25 ("/api/health detects
    # database failure"). A genuinely missing/never-built database must
    # now report "unavailable", not the stale placeholder value. The
    # nonexistent path is explicit (not the default) so this test is
    # deterministic regardless of whatever ambient dev-generated DB file
    # may or may not exist on disk.
    missing_db_path = str(tmp_path / "does_not_exist.db")
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, price_db_path=missing_db_path)
    try:
        client = TestClient(app)
        response = client.get("/api/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["database"] == "unavailable"
        assert body["providers"] == {"recipeapi_io": "not_configured", "llm": "not_configured"}
    finally:
        app.dependency_overrides.clear()


def test_health_reports_database_ok_when_reference_db_is_reachable(tmp_path):
    db_path = str(tmp_path / "healthy.db")
    with connection_scope(db_path, read_only=False) as connection:
        create_schema(connection)

    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, price_db_path=db_path)
    try:
        client = TestClient(app)
        response = client.get("/api/health")
        body = response.json()
        assert body["database"] == "ok"
    finally:
        app.dependency_overrides.clear()


def test_health_reports_database_unavailable_for_a_corrupt_file(tmp_path):
    # A health check must degrade safely rather than crash the app when
    # the configured path exists but is not a valid SQLite database.
    corrupt_db_path = tmp_path / "corrupt.db"
    corrupt_db_path.write_text("this is not a sqlite database")

    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, price_db_path=str(corrupt_db_path))
    try:
        client = TestClient(app)
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["database"] == "unavailable"
    finally:
        app.dependency_overrides.clear()


def test_health_reports_configured_providers_without_leaking_secrets(tmp_path):
    missing_db_path = str(tmp_path / "does_not_exist.db")
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        price_db_path=missing_db_path,
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


# -- 2026-09-13 security hardening patch -----------------------------------


def test_health_in_production_returns_only_status(tmp_path):
    missing_db_path = str(tmp_path / "does_not_exist.db")
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        price_db_path=missing_db_path,
        environment="production",
        anthropic_api_key="sk-secret-value",
        recipeapi_io_api_key="rk-secret-value",
    )
    try:
        client = TestClient(app)
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "database": None, "providers": None, "build_version": None}
    finally:
        app.dependency_overrides.clear()


def test_health_in_production_never_reveals_provider_or_database_state(tmp_path):
    missing_db_path = str(tmp_path / "does_not_exist.db")
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        price_db_path=missing_db_path,
        environment="production",
        anthropic_api_key="sk-secret-value",
        recipeapi_io_api_key="rk-secret-value",
    )
    try:
        client = TestClient(app)
        response = client.get("/api/health")
        body = response.text
        for leaked in ("configured", "not_configured", "unavailable", "sk-secret-value", "rk-secret-value"):
            assert leaked not in body
    finally:
        app.dependency_overrides.clear()


def test_health_in_development_keeps_existing_detailed_response(tmp_path):
    # Unchanged behavior -- development/test callers still see the
    # existing detailed shape (default environment, no override needed).
    db_path = str(tmp_path / "healthy.db")
    with connection_scope(db_path, read_only=False) as connection:
        create_schema(connection)
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, price_db_path=db_path)
    try:
        client = TestClient(app)
        response = client.get("/api/health")
        body = response.json()
        assert body["database"] == "ok"
        assert body["providers"] == {"recipeapi_io": "not_configured", "llm": "not_configured"}
    finally:
        app.dependency_overrides.clear()
