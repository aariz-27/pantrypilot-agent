"""Ticket section 41: explicit admin security tests -- SQL-like input,
HTML/script-like ingredient names, very long strings, direct
unauthenticated access, malformed sessions, bad CSRF tokens.
"""

from __future__ import annotations

from tests.admin.conftest import ADMIN_USERNAME, admin_headers


def test_direct_unauthenticated_ingredients_request_rejected(admin_client):
    response = admin_client.get("/api/admin/ingredients")
    assert response.status_code == 401


def test_direct_unauthenticated_price_create_rejected(admin_client):
    response = admin_client.post(
        "/api/admin/ingredients/tomato/prices",
        json={"normalized_unit": "g", "display_name": "Tomato", "normalized_price_per_unit": 1.0, "provenance_note": "x"},
    )
    assert response.status_code == 401


def test_direct_unauthenticated_audit_rejected(admin_client):
    assert admin_client.get("/api/admin/audit").status_code == 401


def test_sql_like_ingredient_name_does_not_break_query_or_inject(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    payload = "onion'; DROP TABLE canonical_ingredients; --"
    response = client.post(
        "/api/admin/ingredients",
        json={"canonical_id": "sql_test_ingredient", "display_name": payload, "default_unit": "g"},
        cookies=cookies,
        headers=admin_headers(csrf),
    )
    assert response.status_code == 201
    assert response.json()["display_name"] == payload

    # The table must still exist and be queryable -- parameterized
    # queries (app.repositories.admin_ingredient_repository) never
    # interpolate raw strings into SQL.
    listing = client.get("/api/admin/ingredients", cookies=cookies)
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1


def test_html_script_like_ingredient_name_stored_and_returned_verbatim_never_executed(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    payload = "<script>alert('xss')</script>"
    response = client.post(
        "/api/admin/ingredients",
        json={"canonical_id": "xss_test_ingredient", "display_name": payload, "default_unit": "g"},
        cookies=cookies,
        headers=admin_headers(csrf),
    )
    assert response.status_code == 201
    # FastAPI/Pydantic JSON responses are never HTML-rendered server-side
    # -- the raw text is returned as a JSON string value, which the
    # React frontend renders via JSX text content (auto-escaped), never
    # dangerouslySetInnerHTML. This test proves the backend stores/
    # returns it verbatim rather than silently mutating or rejecting it
    # -- XSS safety itself is enforced on the frontend rendering side.
    assert response.json()["display_name"] == payload


def test_very_long_display_name_rejected(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    response = client.post(
        "/api/admin/ingredients",
        json={"canonical_id": "long_name_ingredient", "display_name": "x" * 5000, "default_unit": "g"},
        cookies=cookies,
        headers=admin_headers(csrf),
    )
    assert response.status_code == 422


def test_very_long_canonical_id_rejected(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    response = client.post(
        "/api/admin/ingredients",
        json={"canonical_id": "x" * 500, "display_name": "Test", "default_unit": "g"},
        cookies=cookies,
        headers=admin_headers(csrf),
    )
    assert response.status_code == 422


def test_negative_and_extreme_prices_rejected(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    client.post(
        "/api/admin/ingredients",
        json={"canonical_id": "extreme_test", "display_name": "Extreme Test", "default_unit": "g"},
        cookies=cookies,
        headers=admin_headers(csrf),
    )
    for bad_price in (-1.0, 0.0):
        response = client.post(
            "/api/admin/ingredients/extreme_test/prices",
            json={
                "normalized_unit": "g", "display_name": "Extreme Test", "normalized_price_per_unit": bad_price,
                "provenance_note": "test",
            },
            cookies=cookies,
            headers=admin_headers(csrf),
        )
        assert response.status_code == 422


def test_invalid_unit_rejected(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    client.post(
        "/api/admin/ingredients",
        json={"canonical_id": "unit_test", "display_name": "Unit Test", "default_unit": "g"},
        cookies=cookies,
        headers=admin_headers(csrf),
    )
    response = client.post(
        "/api/admin/ingredients/unit_test/prices",
        json={
            "normalized_unit": "<script>", "display_name": "Unit Test", "normalized_price_per_unit": 1.0,
            "provenance_note": "test",
        },
        cookies=cookies,
        headers=admin_headers(csrf),
    )
    assert response.status_code == 422


def test_repeated_login_failures_eventually_rate_limited(admin_client):
    statuses = [
        admin_client.post("/api/admin/auth/login", json={"username": ADMIN_USERNAME, "password": f"wrong-{i}"}).status_code
        for i in range(10)
    ]
    assert all(status in (401, 429) for status in statuses)
    assert 429 in statuses


def test_bad_csrf_token_rejected_with_valid_session(logged_in_admin):
    client, cookies, _csrf = logged_in_admin
    response = client.post(
        "/api/admin/ingredients",
        json={"canonical_id": "csrf_test", "display_name": "Csrf Test", "default_unit": "g"},
        cookies=cookies,
        headers=admin_headers("forged-token-value"),
    )
    assert response.status_code == 403


def test_forged_session_cookie_rejected(admin_client):
    admin_client.cookies.set("pp_admin_session", "forged-session-id.forged-signature")
    response = admin_client.get("/api/admin/ingredients")
    assert response.status_code == 401
