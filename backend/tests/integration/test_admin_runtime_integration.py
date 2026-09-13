"""End-to-end proof that admin-managed ingredients/aliases/prices reach
the PUBLIC application (ticket section 29 F/G, "Final Runtime Ingredient
Integration" ticket, 2026-09-13) -- exercised through the real FastAPI
app and real HTTP routes (admin + public), not just the underlying
repository functions (see tests/unit/test_runtime_ingredient_repository.py
for those).
"""

from __future__ import annotations

from app.admin.security import hash_password
from app.config import Settings, get_settings
from app.db.admin_schema import create_admin_schema
from app.db.connection import connection_scope
from app.db.schema import create_schema
from app.main import app
from app.repositories.runtime_ingredient_repository import invalidate_runtime_ingredient_cache
from fastapi.testclient import TestClient


def _settings(db_path: str) -> Settings:
    return Settings(
        _env_file=None,
        price_db_path=db_path,
        admin_username="founder",
        admin_password_hash=hash_password("test-password-value"),
        admin_session_secret="test-session-secret-thats-long-enough-for-validation",
    )


def _login(client: TestClient) -> tuple[dict, str]:
    response = client.post("/api/admin/auth/login", json={"username": "founder", "password": "test-password-value"})
    assert response.status_code == 200, response.text
    return response.cookies, response.json()["csrf_token"]


def test_admin_created_ingredient_and_alias_appear_in_public_autocomplete(tmp_path):
    db_path = str(tmp_path / "runtime_integration.db")
    with connection_scope(db_path, read_only=False) as connection:
        create_schema(connection)
        create_admin_schema(connection)
    invalidate_runtime_ingredient_cache()

    app.dependency_overrides[get_settings] = lambda: _settings(db_path)
    try:
        client = TestClient(app)
        cookies, csrf = _login(client)

        create_response = client.post(
            "/api/admin/ingredients",
            json={"canonical_id": "dragonfruit_admin_test", "display_name": "Dragonfruit Admin Test", "default_unit": "g"},
            cookies=cookies,
            headers={"x-admin-csrf-token": csrf},
        )
        assert create_response.status_code == 201

        alias_response = client.post(
            "/api/admin/ingredients/dragonfruit_admin_test/aliases",
            json={"alias": "synthetic test alias"},
            cookies=cookies,
            headers={"x-admin-csrf-token": csrf},
        )
        assert alias_response.status_code == 201

        # Public, unauthenticated autocomplete now recognizes both the
        # new canonical ingredient's display name AND its admin-created
        # alias -- ticket section 29-A/B, exercised through the real
        # public route, not the repository function directly.
        by_name = client.get("/api/ingredients/suggest", params={"q": "dragonfruit admin"})
        assert by_name.status_code == 200
        assert any(s["canonical_id"] == "dragonfruit_admin_test" for s in by_name.json()["suggestions"])

        by_alias = client.get("/api/ingredients/suggest", params={"q": "synthetic test alias"})
        assert by_alias.status_code == 200
        assert any(s["canonical_id"] == "dragonfruit_admin_test" for s in by_alias.json()["suggestions"])
    finally:
        app.dependency_overrides.clear()
        invalidate_runtime_ingredient_cache()


def test_deactivated_admin_alias_no_longer_appears_in_public_autocomplete(tmp_path):
    db_path = str(tmp_path / "runtime_integration_deactivate.db")
    with connection_scope(db_path, read_only=False) as connection:
        create_schema(connection)
        create_admin_schema(connection)
    invalidate_runtime_ingredient_cache()

    app.dependency_overrides[get_settings] = lambda: _settings(db_path)
    try:
        client = TestClient(app)
        cookies, csrf = _login(client)
        client.post(
            "/api/admin/ingredients",
            json={"canonical_id": "dragonfruit_admin_test", "display_name": "Dragonfruit Admin Test", "default_unit": "g"},
            cookies=cookies,
            headers={"x-admin-csrf-token": csrf},
        )
        client.post(
            "/api/admin/ingredients/dragonfruit_admin_test/aliases",
            json={"alias": "synthetic test alias"},
            cookies=cookies,
            headers={"x-admin-csrf-token": csrf},
        )
        client.delete(
            "/api/admin/aliases/synthetic%20test%20alias", cookies=cookies, headers={"x-admin-csrf-token": csrf}
        )

        response = client.get("/api/ingredients/suggest", params={"q": "synthetic test alias"})
        assert response.json()["suggestions"] == []
    finally:
        app.dependency_overrides.clear()
        invalidate_runtime_ingredient_cache()


def test_new_canonical_ingredient_with_manual_price_resolves_through_public_pricing_identity(tmp_path):
    # Ticket section 29-G / section 11: admin creates canonical
    # ingredient -> alias -> manual price; the public resolver
    # recognizes the alias and produces the SAME canonical_id the
    # pricing engine already has a manual price for. This proves
    # identity correlation end-to-end without needing a live
    # RecipeAPI.io call or a full orchestrator run -- pricing identity
    # is a pure function of the resolved canonical_id, already proven
    # correct by PriceRepository's own extensive test suite.
    db_path = str(tmp_path / "runtime_integration_pricing.db")
    with connection_scope(db_path, read_only=False) as connection:
        create_schema(connection)
        create_admin_schema(connection)
    invalidate_runtime_ingredient_cache()

    app.dependency_overrides[get_settings] = lambda: _settings(db_path)
    try:
        client = TestClient(app)
        cookies, csrf = _login(client)
        client.post(
            "/api/admin/ingredients",
            json={"canonical_id": "dragonfruit_admin_test", "display_name": "Dragonfruit Admin Test", "default_unit": "g"},
            cookies=cookies,
            headers={"x-admin-csrf-token": csrf},
        )
        client.post(
            "/api/admin/ingredients/dragonfruit_admin_test/aliases",
            json={"alias": "synthetic test alias"},
            cookies=cookies,
            headers={"x-admin-csrf-token": csrf},
        )
        price_response = client.post(
            "/api/admin/ingredients/dragonfruit_admin_test/prices",
            json={
                "normalized_unit": "g", "display_name": "Dragonfruit Admin Test", "normalized_price_per_unit": 0.02,
                "provenance_note": "test",
            },
            cookies=cookies,
            headers={"x-admin-csrf-token": csrf},
        )
        assert price_response.status_code == 201

        # Public autocomplete resolves the alias to the exact canonical
        # id the manual price was stored under.
        suggestion = client.get("/api/ingredients/suggest", params={"q": "synthetic test alias"}).json()["suggestions"][0]
        assert suggestion["canonical_id"] == "dragonfruit_admin_test"

        from app.repositories.price_repository import PriceRepository

        price = PriceRepository(db_path).get_price(suggestion["canonical_id"])
        assert price is not None
        assert price.normalized_price_per_unit == 0.02
        assert price.source_type == "manual_curated"
    finally:
        app.dependency_overrides.clear()
        invalidate_runtime_ingredient_cache()


def test_autocomplete_and_pantry_normalization_agree_on_admin_created_alias(tmp_path):
    # Ticket section 10/29-F: cross-layer consistency -- whatever
    # autocomplete suggests must also be what
    # app.domain.ingredient_normalizer resolves the SAME raw text to,
    # using the SAME merged vocabulary app.agent.orchestrator builds
    # for a live run.
    db_path = str(tmp_path / "runtime_integration_consistency.db")
    with connection_scope(db_path, read_only=False) as connection:
        create_schema(connection)
        create_admin_schema(connection)
    invalidate_runtime_ingredient_cache()

    from app.repositories.admin_ingredient_repository import AdminIngredientRepository
    from app.repositories.runtime_ingredient_repository import get_merged_vocabulary
    from app.domain.ingredient_autocomplete import suggest_ingredients
    from app.domain.ingredient_normalizer import normalize_ingredient_name

    repo = AdminIngredientRepository(db_path)
    repo.create_ingredient(canonical_id="dragonfruit_admin_test", display_name="Dragonfruit Admin Test", default_unit="g", updated_by="founder")
    repo.create_alias(canonical_id="dragonfruit_admin_test", alias_text="synthetic test alias", source="manual", updated_by="founder")

    vocab = get_merged_vocabulary(db_path)
    suggestions = suggest_ingredients("synthetic test alias", canonical_vocabulary=vocab.canonical_ids, aliases=vocab.aliases)
    assert any(s.canonical_id == "dragonfruit_admin_test" for s in suggestions)

    normalization = normalize_ingredient_name("synthetic test alias", vocab.canonical_ids, vocab.aliases)
    assert normalization.canonical_id == "dragonfruit_admin_test"
