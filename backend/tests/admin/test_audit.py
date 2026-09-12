from __future__ import annotations

from tests.admin.conftest import ADMIN_PASSWORD, admin_headers


def _create_ingredient(client, cookies, csrf, canonical_id="test_ginger", display_name="Ginger"):
    return client.post(
        "/api/admin/ingredients",
        json={"canonical_id": canonical_id, "display_name": display_name, "default_unit": "g"},
        cookies=cookies,
        headers=admin_headers(csrf),
    )


def test_login_creates_audit_record(logged_in_admin):
    client, cookies, _csrf = logged_in_admin
    response = client.get("/api/admin/audit", cookies=cookies)
    actions = [item["action"] for item in response.json()["items"]]
    assert "admin_login" in actions


def test_ingredient_create_creates_audit_record(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    _create_ingredient(client, cookies, csrf)
    response = client.get("/api/admin/audit", params={"entity_type": "canonical_ingredient"}, cookies=cookies)
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["action"] == "ingredient_created"
    assert body["items"][0]["entity_id"] == "test_ginger"


def test_alias_and_price_mutations_create_audit_records(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    _create_ingredient(client, cookies, csrf)
    client.post(
        "/api/admin/ingredients/test_ginger/aliases", json={"alias": "root ginger"}, cookies=cookies, headers=admin_headers(csrf)
    )
    client.post(
        "/api/admin/ingredients/test_ginger/prices",
        json={
            "normalized_unit": "g", "display_name": "Ginger", "normalized_price_per_unit": 0.013,
            "provenance_note": "test",
        },
        cookies=cookies,
        headers=admin_headers(csrf),
    )
    response = client.get("/api/admin/audit", cookies=cookies)
    actions = {item["action"] for item in response.json()["items"]}
    assert {"alias_created", "price_created"}.issubset(actions)


def test_audit_log_never_contains_password_or_secrets(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    _create_ingredient(client, cookies, csrf)
    response = client.get("/api/admin/audit", cookies=cookies)
    raw_text = response.text
    assert ADMIN_PASSWORD not in raw_text
    assert csrf not in raw_text


def test_audit_pagination(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    for i in range(5):
        _create_ingredient(client, cookies, csrf, canonical_id=f"spice_{i}", display_name=f"Spice {i}")
    response = client.get("/api/admin/audit", params={"page": 1, "page_size": 3}, cookies=cookies)
    body = response.json()
    assert len(body["items"]) == 3
    assert body["total"] >= 6  # 5 ingredient_created + 1 admin_login


def test_audit_requires_authentication(admin_client):
    response = admin_client.get("/api/admin/audit")
    assert response.status_code == 401
