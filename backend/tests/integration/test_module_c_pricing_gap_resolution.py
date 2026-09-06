"""Regression tests for the final Module C pricing-gap resolution
(2026-09-06): coconut's shredded/whole split, and the exclusion-based
fixes for evaporated_milk, flavoured_yoghurt, fresh_cream, ghee,
ketchup, and whipping_cream. Also proves corn and mayonnaise are
intentionally left unresolved rather than fabricated.

Uses a dedicated fixture (backend/data/fixtures/
module_c_pricing_gap_regression.json), isolated from PP-003's and the
butter/apple/carrot ticket's fixtures.
"""

import os

from app.db.connection import connection_scope
from app.repositories.price_repository import PriceRepository
from scripts.import_lulu_products import import_products
from scripts.normalize_grocery_prices import run_normalization

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "fixtures", "module_c_pricing_gap_regression.json"
)


def _build_db(tmp_path):
    db_path = str(tmp_path / "module_c_pricing_gap_regression.db")
    import_products(FIXTURE_PATH, db_path)
    run_normalization(db_path)
    return db_path


def test_shredded_coconut_splits_and_both_forms_promote(tmp_path):
    db_path = _build_db(tmp_path)
    repo = PriceRepository(db_path)

    coconut = repo.get_price("coconut")
    shredded = repo.get_price("shredded_coconut")

    assert coconut is not None and coconut.normalized_unit == "pcs"
    assert coconut.contributor_count == 2
    assert shredded is not None and shredded.normalized_unit == "g"
    assert shredded.contributor_count == 1
    assert coconut.canonical_id != shredded.canonical_id


def test_evaporated_milk_excludes_portion_pack_but_promotes(tmp_path):
    db_path = _build_db(tmp_path)
    with connection_scope(db_path, read_only=True) as connection:
        portion = connection.execute(
            "SELECT mapping_status, canonical_id, normalized_unit FROM mapped_grocery_products "
            "WHERE title LIKE '%Portion 10 x 14 ml%'"
        ).fetchone()
        assert portion["mapping_status"] == "mapped"
        assert portion["canonical_id"] == "evaporated_milk"
        assert portion["normalized_unit"] == "ml"

    repo = PriceRepository(db_path)
    result = repo.get_price("evaporated_milk")
    assert result is not None
    assert result.normalized_unit == "g"
    assert result.contributor_count == 1


def test_flavoured_yoghurt_excludes_lassi_and_pcs_but_promotes(tmp_path):
    db_path = _build_db(tmp_path)
    repo = PriceRepository(db_path)
    result = repo.get_price("flavoured_yoghurt")
    assert result is not None
    assert result.normalized_unit == "g"
    # Only the single g-based cup contributed; the lassi (ml) and the
    # pcs-only pack were excluded.
    assert result.contributor_count == 1


def test_fresh_cream_excludes_pourable_cream_but_promotes(tmp_path):
    db_path = _build_db(tmp_path)
    repo = PriceRepository(db_path)
    result = repo.get_price("fresh_cream")
    assert result is not None
    assert result.normalized_unit == "g"
    assert result.contributor_count == 1


def test_ghee_restricts_to_volume_basis(tmp_path):
    db_path = _build_db(tmp_path)
    with connection_scope(db_path, read_only=True) as connection:
        g_row = connection.execute(
            "SELECT mapping_status, canonical_id, normalized_unit FROM mapped_grocery_products "
            "WHERE title LIKE '%Almarai Pure Butter Ghee 800 g%'"
        ).fetchone()
        # The weight-labeled ghee stays a genuine `mapped` row -- just
        # excluded from ghee's reference-price statistic.
        assert g_row["mapping_status"] == "mapped"
        assert g_row["canonical_id"] == "ghee"
        assert g_row["normalized_unit"] == "g"

    repo = PriceRepository(db_path)
    result = repo.get_price("ghee")
    assert result is not None
    assert result.normalized_unit == "ml"
    assert result.contributor_count == 1


def test_ketchup_excludes_ml_outlier_but_promotes(tmp_path):
    db_path = _build_db(tmp_path)
    repo = PriceRepository(db_path)
    result = repo.get_price("ketchup")
    assert result is not None
    assert result.normalized_unit == "g"
    assert result.contributor_count == 1


def test_whipping_cream_excludes_spray_but_promotes(tmp_path):
    db_path = _build_db(tmp_path)
    with connection_scope(db_path, read_only=True) as connection:
        spray = connection.execute(
            "SELECT mapping_status, canonical_id, normalized_unit FROM mapped_grocery_products "
            "WHERE title LIKE '%Whipping Cream Spray%'"
        ).fetchone()
        assert spray["mapping_status"] == "mapped"
        assert spray["canonical_id"] == "whipping_cream"
        assert spray["normalized_unit"] == "g"

    repo = PriceRepository(db_path)
    result = repo.get_price("whipping_cream")
    assert result is not None
    assert result.normalized_unit == "ml"
    assert result.contributor_count == 1


def test_corn_and_mayonnaise_remain_unresolved_not_fabricated(tmp_path):
    # Both genuinely lack a non-arbitrary deterministic signal (see
    # grocery_taxonomy.RESIDUAL_INCOMPATIBLE_CANONICAL_IDS) -- must
    # never silently promote a fabricated reference price.
    db_path = _build_db(tmp_path)
    repo = PriceRepository(db_path)
    assert repo.get_price("corn") is None
    assert repo.get_price("mayonnaise") is None


def test_unrelated_pcs_ingredient_eggs_unaffected(tmp_path):
    db_path = _build_db(tmp_path)
    repo = PriceRepository(db_path)
    result = repo.get_price("egg")
    assert result is not None
    assert result.normalized_unit == "pcs"


def test_unknown_canonical_id_still_returns_none_never_zero(tmp_path):
    db_path = _build_db(tmp_path)
    repo = PriceRepository(db_path)
    assert repo.get_price("nonexistent_ingredient_xyz") is None
