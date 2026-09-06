"""Regression tests for the essential-ingredient data-quality fix
(2026-09-06): generic butter's roasting-spray contaminant, apple's
piece-counted contributor, and carrot's missing fixed taxonomy mapping.

Uses a dedicated small fixture (backend/data/fixtures/
butter_apple_carrot_regression.json) rather than the shared PP-003
fixture/tests, so this ticket's coverage is fully isolated and does not
touch or reopen PP-003's existing fixture/assertions.
"""

import os

from app.db.connection import connection_scope
from app.repositories.price_repository import PriceRepository
from scripts.import_lulu_products import import_products
from scripts.normalize_grocery_prices import run_normalization

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "fixtures", "butter_apple_carrot_regression.json"
)


def _build_db(tmp_path):
    db_path = str(tmp_path / "butter_apple_carrot_regression.db")
    import_products(FIXTURE_PATH, db_path)
    run_normalization(db_path)
    return db_path


def test_butter_spray_is_excluded_but_genuine_mass_based_butter_still_promotes(tmp_path):
    db_path = _build_db(tmp_path)

    with connection_scope(db_path, read_only=True) as connection:
        # The spray row remains a genuine `mapped` row (nothing silently
        # dropped from ingestion) -- just excluded from reference pricing.
        spray = connection.execute(
            "SELECT mapping_status, canonical_id, normalized_unit FROM mapped_grocery_products "
            "WHERE title = 'Lurpak Butter Roasting Spray 200 ml'"
        ).fetchone()
        assert spray["mapping_status"] == "mapped"
        assert spray["canonical_id"] == "butter"
        assert spray["normalized_unit"] == "ml"

        price_row = connection.execute(
            "SELECT * FROM ingredient_prices WHERE canonical_id = 'butter'"
        ).fetchone()
        assert price_row is not None
        assert price_row["normalized_unit"] == "g"
        # 3 genuine g-based butter products contributed; the ml spray did not.
        assert price_row["contributor_count"] == 3

    repo = PriceRepository(db_path)
    result = repo.get_price("butter")
    assert result is not None
    assert result.normalized_unit == "g"
    assert result.source_type == "lulu_reference"


def test_apple_pcs_contributor_excluded_but_mass_based_apple_still_promotes(tmp_path):
    db_path = _build_db(tmp_path)

    with connection_scope(db_path, read_only=True) as connection:
        pcs_row = connection.execute(
            "SELECT mapping_status, canonical_id, normalized_unit FROM mapped_grocery_products "
            "WHERE title = 'Rockit Apple 1 pkt 5 pcs'"
        ).fetchone()
        # Kept in mapped data, per Founder instruction -- just excluded
        # from canonical apple's reference-price aggregation.
        assert pcs_row["mapping_status"] == "mapped"
        assert pcs_row["canonical_id"] == "apple"
        assert pcs_row["normalized_unit"] == "pcs"

        price_row = connection.execute(
            "SELECT * FROM ingredient_prices WHERE canonical_id = 'apple'"
        ).fetchone()
        assert price_row is not None
        assert price_row["normalized_unit"] == "g"
        # 3 genuine mass-based apple products contributed; the pcs pack did not.
        assert price_row["contributor_count"] == 3

    repo = PriceRepository(db_path)
    result = repo.get_price("apple")
    assert result is not None
    assert result.normalized_unit == "g"
    assert result.source_type == "lulu_reference"


def test_carrots_producttype_maps_to_canonical_carrot_and_promotes(tmp_path):
    db_path = _build_db(tmp_path)

    with connection_scope(db_path, read_only=True) as connection:
        rows = connection.execute(
            "SELECT canonical_id, mapping_status FROM mapped_grocery_products WHERE product_type = 'Carrots'"
        ).fetchall()
        assert len(rows) == 2
        assert all(r["mapping_status"] == "mapped" and r["canonical_id"] == "carrot" for r in rows)

    repo = PriceRepository(db_path)
    result = repo.get_price("carrot")
    assert result is not None
    assert result.source_type == "lulu_reference"
    assert result.contributor_count == 2


def test_unrelated_pcs_ingredient_eggs_is_unaffected_by_the_apple_exclusion(tmp_path):
    # The apple exclusion is scoped to canonical_id "apple" only -- eggs
    # (correctly priced per-piece) must be completely unaffected.
    db_path = _build_db(tmp_path)

    repo = PriceRepository(db_path)
    result = repo.get_price("egg")
    assert result is not None
    assert result.normalized_unit == "pcs"
    assert result.source_type == "lulu_reference"


def test_unknown_canonical_id_still_returns_none_never_zero(tmp_path):
    db_path = _build_db(tmp_path)
    repo = PriceRepository(db_path)
    assert repo.get_price("nonexistent_ingredient_xyz") is None


def test_salted_and_unsalted_butter_manual_entries_unaffected_by_generic_butter_now_promoting(tmp_path):
    # Once generic "butter" gets a real lulu_reference price (after the
    # spray exclusion fix), the separate salted_butter/unsalted_butter
    # manual entries must remain untouched, distinct, and still resolve
    # via manual_curated -- generic butter promoting a price must never
    # substitute for or shadow the variant-specific manual entries.
    db_path = _build_db(tmp_path)
    with connection_scope(db_path, read_only=False) as connection:
        connection.executemany(
            """
            INSERT INTO manual_price_entries (
                canonical_id, normalized_unit, display_name, normalized_price_per_unit,
                package_quantity, package_unit, package_price_aed, normalized_package_quantity,
                source_type, provenance_note, collected_at
            ) VALUES (?, 'g', ?, 0.06925, 200, 'g', 13.85, 200, 'manual_curated', 'Founder-approved manual price', '2026-09-06')
            """,
            [
                ("unsalted_butter", "Unsalted Butter"),
                ("salted_butter", "Salted Butter"),
            ],
        )
        connection.commit()

    repo = PriceRepository(db_path)
    butter = repo.get_price("butter")
    unsalted = repo.get_price("unsalted_butter")
    salted = repo.get_price("salted_butter")

    assert butter is not None and butter.source_type == "lulu_reference"
    assert unsalted is not None and unsalted.source_type == "manual_curated"
    assert salted is not None and salted.source_type == "manual_curated"
    assert len({butter.canonical_id, unsalted.canonical_id, salted.canonical_id}) == 3
