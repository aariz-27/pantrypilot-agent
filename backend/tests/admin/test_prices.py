from __future__ import annotations

import json

from app.db.connection import connection_scope
from tests.admin.conftest import admin_headers


def _create_ingredient(client, cookies, csrf, canonical_id="tomato", display_name="Tomato"):
    return client.post(
        "/api/admin/ingredients",
        json={"canonical_id": canonical_id, "display_name": display_name, "default_unit": "g"},
        cookies=cookies,
        headers=admin_headers(csrf),
    )


def _create_price(client, cookies, csrf, canonical_id="tomato", price=0.02, unit="g"):
    return client.post(
        f"/api/admin/ingredients/{canonical_id}/prices",
        json={
            "normalized_unit": unit,
            "display_name": "Tomato",
            "normalized_price_per_unit": price,
            "package_quantity": 1000,
            "package_unit": "g",
            "package_price_aed": 20.0,
            "normalized_package_quantity": 1000,
            "provenance_note": "Manually verified, test fixture.",
        },
        cookies=cookies,
        headers=admin_headers(csrf),
    )


def test_add_manual_price_success(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    _create_ingredient(client, cookies, csrf)
    response = _create_price(client, cookies, csrf)
    assert response.status_code == 201
    body = response.json()
    assert body["normalized_price_per_unit"] == 0.02
    assert body["source_type"] == "manual_curated"
    assert body["active"] is True


def test_add_duplicate_active_manual_price_rejected(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    _create_ingredient(client, cookies, csrf)
    _create_price(client, cookies, csrf)
    response = _create_price(client, cookies, csrf)
    assert response.status_code == 409


def test_update_manual_price(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    _create_ingredient(client, cookies, csrf)
    _create_price(client, cookies, csrf)
    response = client.patch(
        "/api/admin/prices/tomato/g",
        json={"normalized_price_per_unit": 0.03},
        cookies=cookies,
        headers=admin_headers(csrf),
    )
    assert response.status_code == 200
    assert response.json()["normalized_price_per_unit"] == 0.03


def test_negative_price_rejected(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    _create_ingredient(client, cookies, csrf)
    response = _create_price(client, cookies, csrf, price=-1.0)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ADMIN_VALIDATION_ERROR"


def test_zero_price_rejected(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    _create_ingredient(client, cookies, csrf)
    response = _create_price(client, cookies, csrf, price=0.0)
    assert response.status_code == 422


def _post_raw_json(client, url, body_dict, cookies, csrf):
    # httpx's own `json=` parameter refuses to encode NaN/Infinity
    # (stricter than stdlib json.dumps' default allow_nan=True) --
    # exactly like a real browser's JSON.stringify would produce
    # `null`, never a literal NaN/Infinity token, so this can never
    # actually arrive from a real frontend either. This helper
    # simulates a non-browser client that sends the non-standard
    # tokens directly, to prove the server-side validation
    # (app.repositories.admin_price_repository._validate_positive_finite)
    # is real defense-in-depth and not only relying on the transport
    # layer's own restriction.
    raw_bytes = json.dumps(body_dict, allow_nan=True).encode("utf-8")
    headers = {**admin_headers(csrf), "content-type": "application/json"}
    return client.post(url, content=raw_bytes, cookies=cookies, headers=headers)


def test_nan_price_rejected(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    _create_ingredient(client, cookies, csrf)
    response = _post_raw_json(
        client,
        "/api/admin/ingredients/tomato/prices",
        {
            "normalized_unit": "g",
            "display_name": "Tomato",
            "normalized_price_per_unit": float("nan"),
            "provenance_note": "test",
        },
        cookies,
        csrf,
    )
    # Never silently treated as zero (DEC-007) -- must be an explicit
    # rejection either at Pydantic/JSON parsing or in the repository's
    # own finite-value check.
    assert response.status_code in (400, 422)


def test_infinite_price_rejected(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    _create_ingredient(client, cookies, csrf)
    response = _post_raw_json(
        client,
        "/api/admin/ingredients/tomato/prices",
        {
            "normalized_unit": "g",
            "display_name": "Tomato",
            "normalized_price_per_unit": float("inf"),
            "provenance_note": "test",
        },
        cookies,
        csrf,
    )
    assert response.status_code in (400, 422)


def test_unsupported_unit_rejected(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    _create_ingredient(client, cookies, csrf)
    response = _create_price(client, cookies, csrf, unit="bunch")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ADMIN_VALIDATION_ERROR"


def test_impossible_package_quantity_rejected(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    _create_ingredient(client, cookies, csrf)
    response = client.post(
        "/api/admin/ingredients/tomato/prices",
        json={
            "normalized_unit": "g",
            "display_name": "Tomato",
            "normalized_price_per_unit": 0.02,
            "package_quantity": -500,
            "provenance_note": "test",
        },
        cookies=cookies,
        headers=admin_headers(csrf),
    )
    assert response.status_code == 422


def test_deactivate_manual_price(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    _create_ingredient(client, cookies, csrf)
    _create_price(client, cookies, csrf)
    response = client.delete("/api/admin/prices/tomato/g", cookies=cookies, headers=admin_headers(csrf))
    assert response.status_code == 200
    assert response.json()["active"] is False

    listing = client.get("/api/admin/ingredients/tomato/prices", cookies=cookies)
    assert listing.json()["manual_prices"] == []


def test_effective_reference_price_shown_alongside_manual(logged_in_admin, admin_db_path):
    client, cookies, csrf = logged_in_admin
    _create_ingredient(client, cookies, csrf)
    with connection_scope(admin_db_path, read_only=False) as connection:
        connection.execute(
            """
            INSERT INTO ingredient_prices (
                canonical_id, normalized_unit, display_name, normalized_price_per_unit,
                package_quantity, package_unit, package_price_aed, normalized_package_quantity,
                contributor_count, aggregation_basis, source_name, source_product_name,
                source_url, collected_at
            ) VALUES ('tomato', 'g', 'tomato', 0.018, 1000, 'g', 18.0, 1000, 3, 'median_odd',
                      'lulu_uae', 'Tomato 1kg', 'https://example.test/tomato', '2026-09-06')
            """
        )
        connection.commit()

    _create_price(client, cookies, csrf, price=0.02)

    response = client.get("/api/admin/ingredients/tomato/prices", cookies=cookies)
    body = response.json()
    assert len(body["reference_prices"]) == 1
    assert body["reference_prices"][0]["normalized_price_per_unit"] == 0.018
    assert len(body["manual_prices"]) == 1
    assert body["manual_prices"][0]["normalized_price_per_unit"] == 0.02


def test_unknown_price_never_reported_as_zero(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    _create_ingredient(client, cookies, csrf, canonical_id="obscure_spice", display_name="Obscure Spice")
    response = client.get("/api/admin/ingredients/obscure_spice/prices", cookies=cookies)
    body = response.json()
    assert body["reference_prices"] == []
    assert body["manual_prices"] == []
    # No entry at all -- never a fabricated {"price": 0}.
