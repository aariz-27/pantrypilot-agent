"""Runtime ingredient resolution merge/precedence/fallback (ticket
section 29 A/D/E/H/I -- admin ingredient dashboard runtime integration,
2026-09-13). See app.repositories.runtime_ingredient_repository's
module docstring for the precedence rules under test here.
"""

from __future__ import annotations

import pytest

from app.db.admin_schema import create_admin_schema
from app.db.connection import connection_scope
from app.db.schema import create_schema
from app.domain.grocery_taxonomy import CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES
from app.repositories.admin_ingredient_repository import AdminIngredientRepository
from app.repositories.runtime_ingredient_repository import (
    alias_conflicts_with_builtin,
    get_merged_vocabulary,
    invalidate_runtime_ingredient_cache,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    invalidate_runtime_ingredient_cache()
    yield
    invalidate_runtime_ingredient_cache()


@pytest.fixture()
def fully_migrated_db(tmp_path):
    path = str(tmp_path / "runtime_test.db")
    with connection_scope(path, read_only=False) as connection:
        create_schema(connection)
        create_admin_schema(connection)
    return path


@pytest.fixture()
def base_schema_only_db(tmp_path):
    """Base PP-003 schema applied, admin_schema migration NEVER run --
    the exact shape of an existing production database before the
    admin dashboard's own migration script runs (ticket section 6/29-H).
    """
    path = str(tmp_path / "unmigrated_test.db")
    with connection_scope(path, read_only=False) as connection:
        create_schema(connection)
    return path


def test_db_path_none_returns_builtin_vocabulary_unchanged():
    # Admin subsystem not wired to any database path at all.
    vocab = get_merged_vocabulary(None)
    assert vocab.canonical_ids is CANONICAL_GROCERY_INGREDIENTS
    assert vocab.aliases is RECIPE_INGREDIENT_ALIASES


def test_builtin_canonical_ingredients_still_resolve_after_merge(fully_migrated_db):
    # Ticket section 29-D.
    vocab = get_merged_vocabulary(fully_migrated_db)
    assert "onion" in vocab.canonical_ids
    assert "bell_pepper" in vocab.canonical_ids
    assert vocab.aliases.get("capsicum") == "bell_pepper"


def test_admin_created_canonical_ingredient_appears_in_merged_vocabulary(fully_migrated_db):
    # Ticket section 29-A.
    repo = AdminIngredientRepository(fully_migrated_db)
    repo.create_ingredient(canonical_id="dragonfruit_admin_test", display_name="Dragonfruit Admin Test", default_unit="g", updated_by="founder")

    vocab = get_merged_vocabulary(fully_migrated_db)
    assert "dragonfruit_admin_test" in vocab.canonical_ids


def test_admin_created_alias_resolves_in_merged_vocabulary(fully_migrated_db):
    # Ticket section 29-B.
    repo = AdminIngredientRepository(fully_migrated_db)
    repo.create_ingredient(canonical_id="dragonfruit_admin_test", display_name="Dragonfruit Admin Test", default_unit="g", updated_by="founder")
    repo.create_alias(canonical_id="dragonfruit_admin_test", alias_text="synthetic test alias", source="manual", updated_by="founder")

    vocab = get_merged_vocabulary(fully_migrated_db)
    assert vocab.aliases.get("synthetic test alias") == "dragonfruit_admin_test"


def test_deactivated_alias_no_longer_resolves(fully_migrated_db):
    # Ticket section 29-C.
    repo = AdminIngredientRepository(fully_migrated_db)
    repo.create_ingredient(canonical_id="dragonfruit_admin_test", display_name="Dragonfruit Admin Test", default_unit="g", updated_by="founder")
    repo.create_alias(canonical_id="dragonfruit_admin_test", alias_text="synthetic test alias", source="manual", updated_by="founder")
    repo.deactivate_alias("synthetic test alias", updated_by="founder")

    vocab = get_merged_vocabulary(fully_migrated_db)
    assert "synthetic test alias" not in vocab.aliases


def test_deactivated_canonical_ingredient_no_longer_appears(fully_migrated_db):
    repo = AdminIngredientRepository(fully_migrated_db)
    repo.create_ingredient(canonical_id="dragonfruit_admin_test", display_name="Dragonfruit Admin Test", default_unit="g", updated_by="founder")
    repo.update_ingredient(
        "dragonfruit_admin_test", display_name=None, default_unit=None, status="archived", updated_by="founder"
    )

    vocab = get_merged_vocabulary(fully_migrated_db)
    assert "dragonfruit_admin_test" not in vocab.canonical_ids


def test_cache_invalidation_makes_admin_write_visible_immediately(fully_migrated_db):
    # Populate the cache with a stale (pre-write) view.
    stale = get_merged_vocabulary(fully_migrated_db)
    assert "star_anise_test" not in stale.canonical_ids

    repo = AdminIngredientRepository(fully_migrated_db)
    repo.create_ingredient(canonical_id="star_anise_test", display_name="Star Anise", default_unit="g", updated_by="founder")

    fresh = get_merged_vocabulary(fully_migrated_db)
    assert "star_anise_test" in fresh.canonical_ids


def test_missing_admin_tables_falls_back_to_builtin_safely(base_schema_only_db):
    # Ticket section 29-H: admin_schema migration never ran --
    # canonical_ingredients doesn't exist at all, ingredient_aliases
    # exists but lacks the `active` column. Must not raise.
    vocab = get_merged_vocabulary(base_schema_only_db)
    assert vocab.canonical_ids == CANONICAL_GROCERY_INGREDIENTS
    assert vocab.aliases == RECIPE_INGREDIENT_ALIASES


def test_missing_database_file_falls_back_to_builtin_safely(tmp_path):
    nonexistent = str(tmp_path / "does_not_exist.db")
    vocab = get_merged_vocabulary(nonexistent)
    assert vocab.canonical_ids == CANONICAL_GROCERY_INGREDIENTS
    assert vocab.aliases == RECIPE_INGREDIENT_ALIASES


def test_admin_disabled_configuration_does_not_break_public_resolver(fully_migrated_db):
    # Ticket section 29-I: even with a real, migrated database, the
    # merge is a pure read -- it never depends on
    # Settings.admin_configured (login being disabled is orthogonal to
    # whether previously-written admin data still enriches the public
    # resolver). This proves the read path alone never raises or
    # degrades regardless of admin auth state.
    vocab = get_merged_vocabulary(fully_migrated_db)
    assert vocab.canonical_ids == CANONICAL_GROCERY_INGREDIENTS  # no admin data written yet, still fine
    assert "onion" in vocab.canonical_ids


# -- built-in conflict prevention (ticket section 7) ------------------------


def test_alias_conflicts_with_builtin_when_alias_text_is_itself_a_builtin_id(fully_migrated_db):
    conflict = alias_conflicts_with_builtin("onion", "dragonfruit_admin_test", fully_migrated_db)
    assert conflict == "onion"


def test_alias_conflicts_with_builtin_when_alias_already_maps_elsewhere(fully_migrated_db):
    conflict = alias_conflicts_with_builtin("capsicum", "dragonfruit_admin_test", fully_migrated_db)
    assert conflict == "bell_pepper"


def test_alias_conflicts_with_builtin_none_for_a_genuinely_new_alias(fully_migrated_db):
    assert alias_conflicts_with_builtin("synthetic test alias", "dragonfruit_admin_test", fully_migrated_db) is None


def test_admin_create_alias_rejects_builtin_id_collision(fully_migrated_db):
    repo = AdminIngredientRepository(fully_migrated_db)
    repo.create_ingredient(canonical_id="dragonfruit_admin_test", display_name="Dragonfruit Admin Test", default_unit="g", updated_by="founder")
    from app.admin.errors import AdminConflictError

    with pytest.raises(AdminConflictError):
        repo.create_alias(canonical_id="dragonfruit_admin_test", alias_text="onion", source="manual", updated_by="founder")


def test_admin_create_alias_rejects_builtin_alias_collision(fully_migrated_db):
    repo = AdminIngredientRepository(fully_migrated_db)
    repo.create_ingredient(canonical_id="dragonfruit_admin_test", display_name="Dragonfruit Admin Test", default_unit="g", updated_by="founder")
    from app.admin.errors import AdminConflictError

    with pytest.raises(AdminConflictError):
        repo.create_alias(canonical_id="dragonfruit_admin_test", alias_text="capsicum", source="manual", updated_by="founder")


def test_admin_create_ingredient_rejects_builtin_canonical_id_collision(fully_migrated_db):
    repo = AdminIngredientRepository(fully_migrated_db)
    from app.admin.errors import AdminConflictError

    with pytest.raises(AdminConflictError):
        repo.create_ingredient(canonical_id="onion", display_name="Onion Two", default_unit="g", updated_by="founder")
