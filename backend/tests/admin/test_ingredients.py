from __future__ import annotations

from tests.admin.conftest import admin_headers


def _create_ingredient(client, cookies, csrf, canonical_id="bell_pepper", display_name="Bell Pepper", default_unit="g"):
    return client.post(
        "/api/admin/ingredients",
        json={"canonical_id": canonical_id, "display_name": display_name, "default_unit": default_unit},
        cookies=cookies,
        headers=admin_headers(csrf),
    )


def test_create_ingredient_success(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    response = _create_ingredient(client, cookies, csrf)
    assert response.status_code == 201
    body = response.json()
    assert body["canonical_id"] == "bell_pepper"
    assert body["status"] == "active"
    assert body["alias_count"] == 0


def test_create_ingredient_duplicate_rejected(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    _create_ingredient(client, cookies, csrf)
    response = _create_ingredient(client, cookies, csrf)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ADMIN_CONFLICT"


def test_create_ingredient_rejects_invalid_canonical_id_format(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    response = _create_ingredient(client, cookies, csrf, canonical_id="Bell Pepper!")
    assert response.status_code in (409, 422)


def test_create_ingredient_rejects_empty_display_name(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    response = client.post(
        "/api/admin/ingredients",
        json={"canonical_id": "onion", "display_name": "", "default_unit": "g"},
        cookies=cookies,
        headers=admin_headers(csrf),
    )
    assert response.status_code == 422


def test_list_ingredients_search_by_canonical_and_alias(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    _create_ingredient(client, cookies, csrf, canonical_id="bell_pepper", display_name="Bell Pepper")
    client.post(
        "/api/admin/ingredients/bell_pepper/aliases", json={"alias": "capsicum"}, cookies=cookies, headers=admin_headers(csrf)
    )

    by_canonical = client.get("/api/admin/ingredients", params={"q": "bell"}, cookies=cookies)
    assert by_canonical.status_code == 200
    assert len(by_canonical.json()["items"]) == 1

    by_alias = client.get("/api/admin/ingredients", params={"q": "capsicum"}, cookies=cookies)
    assert by_alias.status_code == 200
    assert by_alias.json()["items"][0]["canonical_id"] == "bell_pepper"

    no_match = client.get("/api/admin/ingredients", params={"q": "nonexistent-xyz"}, cookies=cookies)
    assert no_match.json()["items"] == []


def test_list_ingredients_pagination(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    for i in range(5):
        _create_ingredient(client, cookies, csrf, canonical_id=f"ingredient_{i}", display_name=f"Ingredient {i}")

    page_1 = client.get("/api/admin/ingredients", params={"page": 1, "page_size": 2}, cookies=cookies)
    assert page_1.status_code == 200
    body = page_1.json()
    assert len(body["items"]) == 2
    assert body["total"] == 5

    page_3 = client.get("/api/admin/ingredients", params={"page": 3, "page_size": 2}, cookies=cookies)
    assert len(page_3.json()["items"]) == 1


def test_edit_ingredient_display_name_and_status(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    _create_ingredient(client, cookies, csrf)
    response = client.patch(
        "/api/admin/ingredients/bell_pepper",
        json={"display_name": "Bell Peppers (Capsicum)", "status": "archived"},
        cookies=cookies,
        headers=admin_headers(csrf),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Bell Peppers (Capsicum)"
    assert body["status"] == "archived"
    assert body["canonical_id"] == "bell_pepper"  # immutable


def test_edit_ingredient_rejects_invalid_status(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    _create_ingredient(client, cookies, csrf)
    response = client.patch(
        "/api/admin/ingredients/bell_pepper", json={"status": "deleted"}, cookies=cookies, headers=admin_headers(csrf)
    )
    assert response.status_code == 422


def test_edit_nonexistent_ingredient_returns_404(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    response = client.patch(
        "/api/admin/ingredients/does_not_exist", json={"display_name": "X"}, cookies=cookies, headers=admin_headers(csrf)
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ADMIN_NOT_FOUND"


def test_get_ingredient_not_found(logged_in_admin):
    client, cookies, _csrf = logged_in_admin
    response = client.get("/api/admin/ingredients/does_not_exist", cookies=cookies)
    assert response.status_code == 404


# -- aliases ----------------------------------------------------------------


def test_create_alias_success(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    _create_ingredient(client, cookies, csrf)
    response = client.post(
        "/api/admin/ingredients/bell_pepper/aliases", json={"alias": "Capsicum"}, cookies=cookies, headers=admin_headers(csrf)
    )
    assert response.status_code == 201
    body = response.json()
    assert body["alias"] == "capsicum"  # normalized lowercase
    assert body["canonical_id"] == "bell_pepper"


def test_create_alias_for_missing_ingredient_returns_404(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    response = client.post(
        "/api/admin/ingredients/does_not_exist/aliases",
        json={"alias": "capsicum"},
        cookies=cookies,
        headers=admin_headers(csrf),
    )
    assert response.status_code == 404


def test_create_duplicate_alias_same_ingredient_rejected(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    _create_ingredient(client, cookies, csrf)
    client.post(
        "/api/admin/ingredients/bell_pepper/aliases", json={"alias": "capsicum"}, cookies=cookies, headers=admin_headers(csrf)
    )
    response = client.post(
        "/api/admin/ingredients/bell_pepper/aliases", json={"alias": "capsicum"}, cookies=cookies, headers=admin_headers(csrf)
    )
    assert response.status_code == 409


def test_create_alias_conflicting_with_different_ingredient_rejected(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    _create_ingredient(client, cookies, csrf, canonical_id="bell_pepper", display_name="Bell Pepper")
    _create_ingredient(client, cookies, csrf, canonical_id="chili", display_name="Chili")
    client.post(
        "/api/admin/ingredients/bell_pepper/aliases", json={"alias": "pepper"}, cookies=cookies, headers=admin_headers(csrf)
    )
    response = client.post(
        "/api/admin/ingredients/chili/aliases", json={"alias": "pepper"}, cookies=cookies, headers=admin_headers(csrf)
    )
    # Never silently remapped (ticket section 12).
    assert response.status_code == 409
    assert "different canonical ingredient" in response.json()["error"]["message"]


def test_deactivate_alias(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    _create_ingredient(client, cookies, csrf)
    client.post(
        "/api/admin/ingredients/bell_pepper/aliases", json={"alias": "capsicum"}, cookies=cookies, headers=admin_headers(csrf)
    )
    response = client.delete("/api/admin/aliases/capsicum", cookies=cookies, headers=admin_headers(csrf))
    assert response.status_code == 200
    assert response.json()["active"] is False

    active_aliases = client.get("/api/admin/ingredients/bell_pepper/aliases", cookies=cookies)
    assert active_aliases.json() == []

    all_aliases = client.get(
        "/api/admin/ingredients/bell_pepper/aliases", params={"include_inactive": True}, cookies=cookies
    )
    assert len(all_aliases.json()) == 1


def test_reassign_alias_requires_explicit_confirmation(logged_in_admin):
    client, cookies, csrf = logged_in_admin
    _create_ingredient(client, cookies, csrf, canonical_id="bell_pepper", display_name="Bell Pepper")
    _create_ingredient(client, cookies, csrf, canonical_id="chili", display_name="Chili")
    client.post(
        "/api/admin/ingredients/bell_pepper/aliases", json={"alias": "pepper"}, cookies=cookies, headers=admin_headers(csrf)
    )

    unconfirmed = client.patch(
        "/api/admin/aliases/pepper",
        json={"new_canonical_id": "chili", "confirm_reassignment": False},
        cookies=cookies,
        headers=admin_headers(csrf),
    )
    assert unconfirmed.status_code == 409

    confirmed = client.patch(
        "/api/admin/aliases/pepper",
        json={"new_canonical_id": "chili", "confirm_reassignment": True},
        cookies=cookies,
        headers=admin_headers(csrf),
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["canonical_id"] == "chili"
