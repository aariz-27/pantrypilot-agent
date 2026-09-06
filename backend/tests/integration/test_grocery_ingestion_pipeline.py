"""End-to-end raw -> mapped -> reference pipeline test, using the
hand-authored fixture (backend/data/fixtures/lulu_sample.json) -- never
the Founder's real dataset in the automated suite."""

import os

from app.db.connection import connection_scope
from scripts.import_lulu_products import import_products
from scripts.normalize_grocery_prices import run_normalization

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "fixtures", "lulu_sample.json")


def test_full_pipeline_against_fixture(tmp_path):
    db_path = str(tmp_path / "pipeline_test.db")

    batch_id, raw_count = import_products(FIXTURE_PATH, db_path)
    assert raw_count == 19
    assert batch_id.startswith("lulu_uae_")

    stats = run_normalization(db_path)

    assert stats["raw_total"] == 19
    assert stats["duplicate"] == 1
    assert stats["invalid_currency"] == 1
    assert stats["unparseable_price"] == 2
    assert stats["unsupported_unit"] == 2
    assert stats["filtered_out"] == 2  # excluded productType + fully-null record
    assert stats["mapped"] > 0
    assert stats["promoted_reference_entries"] > 0
    assert stats["incompatible_unit_groups"] == 1  # boneless_chicken_breast: g vs pcs

    with connection_scope(db_path, read_only=True) as connection:
        # Every raw row produced exactly one mapped row -- nothing silently dropped.
        mapped_total = connection.execute("SELECT COUNT(*) AS c FROM mapped_grocery_products").fetchone()["c"]
        assert mapped_total == 19

        onion_price = connection.execute(
            "SELECT * FROM ingredient_prices WHERE canonical_id = 'onion'"
        ).fetchone()
        assert onion_price is not None
        assert onion_price["contributor_count"] == 2
        assert onion_price["normalized_unit"] == "g"

        # Incompatible-unit canonical ID must never be promoted.
        chicken = connection.execute(
            "SELECT * FROM ingredient_prices WHERE canonical_id = 'boneless_chicken_breast'"
        ).fetchone()
        assert chicken is None

        # Excluded product type must never appear as MAPPED.
        chocolate = connection.execute(
            "SELECT mapping_status FROM mapped_grocery_products WHERE title LIKE '%Chocolate Bar%'"
        ).fetchone()
        assert chocolate["mapping_status"] == "filtered_out"


def test_reimport_and_renormalize_is_idempotent(tmp_path):
    db_path = str(tmp_path / "idempotent_test.db")
    import_products(FIXTURE_PATH, db_path)
    stats_1 = run_normalization(db_path)
    stats_2 = run_normalization(db_path)
    assert stats_1 == stats_2
