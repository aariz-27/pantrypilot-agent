from __future__ import annotations

from app.db.connection import connection_scope
from tests.admin.conftest import admin_headers


def test_dashboard_summary_requires_auth(admin_client):
    assert admin_client.get("/api/admin/dashboard/summary").status_code == 401


def test_dashboard_summary_counts_reflect_real_data(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    client.post(
        "/api/admin/ingredients",
        json={"canonical_id": "test_onion", "display_name": "Onion", "default_unit": "g"},
        cookies=cookies,
        headers=admin_headers(csrf),
    )
    client.post(
        "/api/admin/ingredients/test_onion/aliases", json={"alias": "onions"}, cookies=cookies, headers=admin_headers(csrf)
    )
    client.post(
        "/api/admin/ingredients/test_onion/prices",
        json={"normalized_unit": "g", "display_name": "Onion", "normalized_price_per_unit": 0.01, "provenance_note": "t"},
        cookies=cookies,
        headers=admin_headers(csrf),
    )

    response = client.get("/api/admin/dashboard/summary", cookies=cookies)
    body = response.json()
    assert body["canonical_ingredient_count"] == 1
    assert body["active_alias_count"] == 1
    assert body["ingredients_with_manual_price"] == 1
    assert body["ingredients_without_known_price"] == 0


def test_dashboard_summary_never_fabricates_grocery_counts_when_no_import_ran(logged_in_admin):
    client, cookies, _csrf = logged_in_admin
    response = client.get("/api/admin/dashboard/summary", cookies=cookies)
    body = response.json()
    assert body["mapped_product_count"] == 0
    assert body["unmapped_product_count"] == 0


def test_grocery_products_read_only_listing(logged_in_admin, admin_db_path):
    client, cookies, _csrf = logged_in_admin
    with connection_scope(admin_db_path, read_only=False) as connection:
        connection.execute(
            """
            INSERT INTO mapped_grocery_products (
                raw_id, source_name, title, brand, canonical_id, mapping_status, imported_at
            ) VALUES (1, 'lulu_uae', 'Fresh Tomato 1kg', 'LuLu', 'tomato', 'mapped', '2026-09-06')
            """
        )
        connection.execute(
            """
            INSERT INTO mapped_grocery_products (
                raw_id, source_name, title, brand, canonical_id, mapping_status, imported_at
            ) VALUES (2, 'lulu_uae', 'Mystery Product XYZ', 'LuLu', NULL, 'unmapped_ingredient', '2026-09-06')
            """
        )
        connection.commit()

    all_products = client.get("/api/admin/grocery/products", cookies=cookies)
    assert all_products.json()["total"] == 2

    mapped_only = client.get("/api/admin/grocery/products", params={"status": "mapped"}, cookies=cookies)
    assert mapped_only.json()["total"] == 1
    assert mapped_only.json()["items"][0]["canonical_id"] == "tomato"

    unmapped_only = client.get("/api/admin/grocery/products", params={"status": "unmapped_ingredient"}, cookies=cookies)
    assert unmapped_only.json()["total"] == 1
    assert unmapped_only.json()["items"][0]["canonical_id"] is None

    search = client.get("/api/admin/grocery/products", params={"q": "mystery"}, cookies=cookies)
    assert search.json()["total"] == 1
