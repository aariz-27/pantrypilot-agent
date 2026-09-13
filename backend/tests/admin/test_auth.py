from __future__ import annotations

from fastapi.testclient import TestClient

from app.admin.security import hash_password
from app.config import Settings, get_settings
from app.main import app as fastapi_app
from tests.admin.conftest import ADMIN_PASSWORD, ADMIN_USERNAME, admin_headers


def test_login_success_sets_httponly_cookie_and_returns_csrf_token(admin_client):
    response = admin_client.post("/api/admin/auth/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == ADMIN_USERNAME
    assert body["csrf_token"]
    assert "pp_admin_session" in response.cookies
    set_cookie_header = response.headers.get("set-cookie", "")
    assert "HttpOnly" in set_cookie_header
    assert "samesite=strict" in set_cookie_header.lower()


def test_login_in_production_sets_secure_cookie(admin_db_path):
    # 2026-09-13 security hardening patch: settings.environment ==
    # "production" is now a validated, closed value (never a silent
    # typo) -- this proves the Secure flag actually follows it end to
    # end through a real login response.
    settings = Settings(
        _env_file=None,
        price_db_path=admin_db_path,
        admin_username=ADMIN_USERNAME,
        admin_password_hash=hash_password(ADMIN_PASSWORD),
        admin_session_secret="a-production-test-session-secret-thats-long-enough",
        environment="production",
    )
    fastapi_app.dependency_overrides[get_settings] = lambda: settings
    try:
        client = TestClient(fastapi_app)
        response = client.post("/api/admin/auth/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        assert response.status_code == 200
        set_cookie_header = response.headers.get("set-cookie", "")
        assert "secure" in set_cookie_header.lower()
    finally:
        fastapi_app.dependency_overrides.clear()


def test_login_invalid_password_returns_generic_401(admin_client):
    response = admin_client.post("/api/admin/auth/login", json={"username": ADMIN_USERNAME, "password": "wrong"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "ADMIN_UNAUTHORIZED"


def test_login_unknown_username_returns_identical_generic_401(admin_client):
    known_user_wrong_pw = admin_client.post("/api/admin/auth/login", json={"username": ADMIN_USERNAME, "password": "wrong"})
    unknown_user = admin_client.post("/api/admin/auth/login", json={"username": "nonexistent", "password": "wrong"})
    assert known_user_wrong_pw.status_code == unknown_user.status_code == 401
    # Never distinguishable which check failed (ticket section 8).
    assert known_user_wrong_pw.json() == unknown_user.json()


def test_admin_not_configured_returns_503(unconfigured_admin_client):
    response = unconfigured_admin_client.post("/api/admin/auth/login", json={"username": "x", "password": "y"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ADMIN_NOT_CONFIGURED"


def test_unauthenticated_request_to_admin_api_rejected(admin_client):
    response = admin_client.get("/api/admin/ingredients")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "ADMIN_UNAUTHORIZED"


def test_malformed_session_cookie_rejected(admin_client):
    admin_client.cookies.set("pp_admin_session", "garbage-not-a-valid-token")
    response = admin_client.get("/api/admin/ingredients")
    assert response.status_code == 401


def test_session_endpoint_returns_current_admin(logged_in_admin):
    client, cookies, _csrf = logged_in_admin
    response = client.get("/api/admin/auth/session", cookies=cookies)
    assert response.status_code == 200
    assert response.json()["username"] == ADMIN_USERNAME


def test_logout_invalidates_session(logged_in_admin):
    client, cookies, csrf_token = logged_in_admin
    logout_response = client.post("/api/admin/auth/logout", cookies=cookies, headers=admin_headers(csrf_token))
    assert logout_response.status_code == 200

    after_logout = client.get("/api/admin/ingredients", cookies=cookies)
    assert after_logout.status_code == 401


def test_logout_requires_csrf_token(logged_in_admin):
    client, cookies, _csrf = logged_in_admin
    response = client.post("/api/admin/auth/logout", cookies=cookies)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ADMIN_CSRF_INVALID"


def test_mutating_request_without_csrf_token_rejected(logged_in_admin):
    client, cookies, _csrf = logged_in_admin
    response = client.post(
        "/api/admin/ingredients", json={"canonical_id": "onion2", "display_name": "Onion 2"}, cookies=cookies
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ADMIN_CSRF_INVALID"


def test_mutating_request_with_wrong_csrf_token_rejected(logged_in_admin):
    client, cookies, _csrf = logged_in_admin
    response = client.post(
        "/api/admin/ingredients",
        json={"canonical_id": "onion2", "display_name": "Onion 2"},
        cookies=cookies,
        headers=admin_headers("totally-wrong-csrf-token"),
    )
    assert response.status_code == 403


def test_login_rate_limited_after_repeated_failures(admin_client):
    # rate_limit_admin_login defaults to "5/minute" (app.config.Settings).
    responses = [
        admin_client.post("/api/admin/auth/login", json={"username": ADMIN_USERNAME, "password": "wrong"})
        for _ in range(6)
    ]
    statuses = [r.status_code for r in responses]
    assert 429 in statuses
