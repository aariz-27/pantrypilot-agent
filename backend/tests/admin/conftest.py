from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.admin.security import hash_password
from app.config import Settings, get_settings
from app.db.admin_schema import create_admin_schema
from app.db.connection import connection_scope
from app.db.schema import create_schema
from app.main import app

ADMIN_USERNAME = "founder"
ADMIN_PASSWORD = "correct horse battery staple"


@pytest.fixture()
def admin_db_path(tmp_path):
    path = str(tmp_path / "admin_test.db")
    with connection_scope(path, read_only=False) as connection:
        create_schema(connection)
        create_admin_schema(connection)
    return path


@pytest.fixture()
def admin_settings(admin_db_path):
    return Settings(
        _env_file=None,
        price_db_path=admin_db_path,
        admin_username=ADMIN_USERNAME,
        admin_password_hash=hash_password(ADMIN_PASSWORD),
        admin_session_secret="unit-test-session-secret-value",
    )


@pytest.fixture()
def admin_client(admin_settings):
    app.dependency_overrides[get_settings] = lambda: admin_settings
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def unconfigured_admin_client(admin_db_path):
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, price_db_path=admin_db_path)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def logged_in_admin(admin_client):
    """Returns (client, cookies, csrf_token) for an already-authenticated admin session."""

    response = admin_client.post("/api/admin/auth/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    assert response.status_code == 200, response.text
    csrf_token = response.json()["csrf_token"]
    return admin_client, response.cookies, csrf_token


def admin_headers(csrf_token: str) -> dict:
    return {"x-admin-csrf-token": csrf_token}
