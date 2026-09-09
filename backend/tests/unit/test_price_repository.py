import os

import pytest

from app.db.connection import connection_scope
from app.db.schema import create_schema
from app.repositories.price_repository import PriceRepository
from scripts.load_manual_price_entries import load_manual_entries

MANUAL_ENTRIES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "manual", "manual_price_entries.json"
)


@pytest.fixture()
def db_path(tmp_path):
    path = str(tmp_path / "test_prices.db")
    with connection_scope(path, read_only=False) as connection:
        create_schema(connection)
        connection.execute(
            """
            INSERT INTO ingredient_prices (
                canonical_id, normalized_unit, display_name, normalized_price_per_unit,
                package_quantity, package_unit, package_price_aed, normalized_package_quantity,
                contributor_count, aggregation_basis, source_name, source_product_name,
                source_url, collected_at
            ) VALUES ('tomato', 'g', 'tomato', 0.02, 1000, 'g', 20.0, 1000, 2, 'median_even',
                      'lulu_uae', 'Tomato 1 kg', 'https://example.test/tomato', '2026-09-06')
            """
        )
        connection.commit()
    return path


def test_get_price_found(db_path):
    repo = PriceRepository(db_path)
    result = repo.get_price("tomato")
    assert result is not None
    assert result.canonical_id == "tomato"
    assert result.normalized_price_per_unit == 0.02
    assert result.package_price_aed == 20.0
    assert result.source_type == "lulu_reference"


def test_get_price_not_found_returns_none_never_zero(db_path):
    repo = PriceRepository(db_path)
    result = repo.get_price("nonexistent_ingredient")
    assert result is None


def test_get_price_falls_back_to_manual_entry(db_path):
    with connection_scope(db_path, read_only=False) as connection:
        connection.execute(
            """
            INSERT INTO manual_price_entries (
                canonical_id, normalized_unit, display_name, normalized_price_per_unit,
                package_quantity, package_unit, package_price_aed, normalized_package_quantity,
                source_type, provenance_note, collected_at
            ) VALUES ('saffron', 'g', 'saffron', 0.45, 1, 'g', 0.45, 1,
                      'manual_curated', 'Manually verified at store X, 2026-09-06', '2026-09-06')
            """
        )
        connection.commit()

    repo = PriceRepository(db_path)
    result = repo.get_price("saffron")
    assert result is not None
    assert result.source_type == "manual_curated"
    assert result.normalized_price_per_unit == 0.45


def test_lulu_reference_takes_precedence_over_manual_entry(db_path):
    with connection_scope(db_path, read_only=False) as connection:
        connection.execute(
            """
            INSERT INTO manual_price_entries (
                canonical_id, normalized_unit, display_name, normalized_price_per_unit,
                package_quantity, package_unit, package_price_aed, normalized_package_quantity,
                source_type, provenance_note, collected_at
            ) VALUES ('tomato', 'g', 'tomato', 999.0, 1, 'g', 999.0, 1,
                      'manual_curated', 'should not be used', '2026-09-06')
            """
        )
        connection.commit()

    repo = PriceRepository(db_path)
    result = repo.get_price("tomato")
    assert result.source_type == "lulu_reference"
    assert result.normalized_price_per_unit == 0.02


def test_repository_never_writes(db_path):
    repo = PriceRepository(db_path)
    repo.get_price("tomato")
    # A second read-only connection must still see exactly the same
    # data -- proving the repository performed no write of its own.
    with connection_scope(db_path, read_only=True) as connection:
        count = connection.execute("SELECT COUNT(*) AS c FROM ingredient_prices").fetchone()["c"]
    assert count == 1


# --- salted/unsalted butter + ginger manual gap-fill (essential-ingredient audit, 2026-09-06) ---


@pytest.fixture()
def db_path_with_butter_variants(db_path):
    with connection_scope(db_path, read_only=False) as connection:
        connection.executemany(
            """
            INSERT INTO manual_price_entries (
                canonical_id, normalized_unit, display_name, normalized_price_per_unit,
                package_quantity, package_unit, package_price_aed, normalized_package_quantity,
                source_type, provenance_note, collected_at
            ) VALUES (?, 'g', ?, 0.06925, 200, 'g', 13.85, 200, 'manual_curated', ?, '2026-09-06')
            """,
            [
                ("unsalted_butter", "Unsalted Butter", "Founder-approved manual price"),
                ("salted_butter", "Salted Butter", "Founder-approved manual price"),
            ],
        )
        connection.commit()
    return db_path


def test_salted_and_unsalted_butter_both_resolve_via_manual_fallback(db_path_with_butter_variants):
    repo = PriceRepository(db_path_with_butter_variants)
    unsalted = repo.get_price("unsalted_butter")
    salted = repo.get_price("salted_butter")
    assert unsalted is not None and unsalted.source_type == "manual_curated"
    assert salted is not None and salted.source_type == "manual_curated"


def test_salted_and_unsalted_butter_remain_distinct_lookups(db_path_with_butter_variants):
    # Founder decision: salted and unsalted butter must never be silently
    # substituted for one another. Looking one up must never accidentally
    # return the other's row.
    repo = PriceRepository(db_path_with_butter_variants)
    unsalted = repo.get_price("unsalted_butter")
    salted = repo.get_price("salted_butter")
    assert unsalted.canonical_id == "unsalted_butter"
    assert salted.canonical_id == "salted_butter"
    assert unsalted.canonical_id != salted.canonical_id


def test_generic_butter_still_not_found_when_only_variants_have_manual_entries(db_path_with_butter_variants):
    # Adding salted_butter/unsalted_butter manual entries must not make
    # generic "butter" resolve to either of them (no silent substitution).
    repo = PriceRepository(db_path_with_butter_variants)
    assert repo.get_price("butter") is None


def test_committed_manual_price_entries_json_loads_and_resolves_all_five_entries(tmp_path):
    # Independent review finding (2026-09-06): prior tests only exercised
    # hand-inserted fixture rows, never the actual committed
    # backend/data/manual/manual_price_entries.json through the real
    # loader. This test loads that exact committed file via the real
    # scripts.load_manual_price_entries.load_manual_entries() entry point
    # and verifies every one of its five Founder-approved entries --
    # including the final Module C closure additions, corn and
    # mayonnaise -- returns the exact expected normalized value through
    # PriceRepository.
    db_path = str(tmp_path / "manual_entries_test.db")

    loaded_count = load_manual_entries(MANUAL_ENTRIES_PATH, db_path)
    # 5 original Founder-approved entries + 19 added by the PR #15
    # controlled canonical + pricing expansion pass (2026-09-09) -- see
    # test_review_needed_expansion.py for the 19 new entries' own
    # dedicated assertions.
    assert loaded_count == 24

    repo = PriceRepository(db_path)

    unsalted = repo.get_price("unsalted_butter")
    assert unsalted is not None
    assert unsalted.source_type == "manual_curated"
    assert unsalted.normalized_unit == "g"
    assert unsalted.normalized_price_per_unit == pytest.approx(0.06925)
    assert unsalted.package_quantity == 200
    assert unsalted.package_price_aed == pytest.approx(13.85)

    salted = repo.get_price("salted_butter")
    assert salted is not None
    assert salted.source_type == "manual_curated"
    assert salted.normalized_unit == "g"
    assert salted.normalized_price_per_unit == pytest.approx(0.06925)
    assert salted.package_quantity == 200
    assert salted.package_price_aed == pytest.approx(13.85)

    ginger = repo.get_price("ginger")
    assert ginger is not None
    assert ginger.source_type == "manual_curated"
    assert ginger.normalized_unit == "g"
    assert ginger.normalized_price_per_unit == pytest.approx(0.01296)
    assert ginger.package_quantity == 250
    assert ginger.package_price_aed == pytest.approx(3.24)

    corn = repo.get_price("corn")
    assert corn is not None
    assert corn.source_type == "manual_curated"
    assert corn.normalized_unit == "g"
    assert corn.normalized_price_per_unit == pytest.approx(0.00995)
    assert corn.package_quantity == 1
    assert corn.package_unit == "kg"
    assert corn.package_price_aed == pytest.approx(9.95)
    assert corn.normalized_package_quantity == pytest.approx(1000)

    mayonnaise = repo.get_price("mayonnaise")
    assert mayonnaise is not None
    assert mayonnaise.source_type == "manual_curated"
    assert mayonnaise.normalized_unit == "g"
    assert mayonnaise.normalized_price_per_unit == pytest.approx(0.0183606557377049, rel=0, abs=1e-16)
    assert mayonnaise.package_quantity == 915
    assert mayonnaise.package_unit == "g"
    assert mayonnaise.package_price_aed == pytest.approx(16.80)
    assert mayonnaise.normalized_package_quantity == pytest.approx(915)

    # Distinctness holds even when loaded from the real committed file.
    assert len({unsalted.canonical_id, salted.canonical_id, ginger.canonical_id, corn.canonical_id, mayonnaise.canonical_id}) == 5


def test_corn_manual_fallback_exact_normalized_price(tmp_path):
    # Founder-approved exact figure: 9.95 AED / 1000 g = 0.00995 AED/g.
    # Never derived from selecting or converting the real LuLu pcs
    # contributor ("Sweet Corn 2 pcs").
    db_path = str(tmp_path / "corn_manual_test.db")
    load_manual_entries(MANUAL_ENTRIES_PATH, db_path)
    result = PriceRepository(db_path).get_price("corn")
    assert result.normalized_price_per_unit == 0.00995
    assert result.normalized_unit == "g"


def test_mayonnaise_manual_fallback_exact_normalized_price(tmp_path):
    # Founder-approved exact figure: 16.80 AED / 915 g = 0.0183606557377049
    # AED/g, stored without arbitrary precision reduction. Never derived
    # from converting or selecting any of the real LuLu ml contributors.
    db_path = str(tmp_path / "mayonnaise_manual_test.db")
    load_manual_entries(MANUAL_ENTRIES_PATH, db_path)
    result = PriceRepository(db_path).get_price("mayonnaise")
    assert result.normalized_price_per_unit == 0.0183606557377049
    assert result.normalized_unit == "g"


def test_corn_and_mayonnaise_manual_fallbacks_never_zero_and_never_pick_ml_or_pcs(tmp_path):
    db_path = str(tmp_path / "corn_mayo_never_zero_test.db")
    load_manual_entries(MANUAL_ENTRIES_PATH, db_path)
    repo = PriceRepository(db_path)
    for canonical_id in ("corn", "mayonnaise"):
        result = repo.get_price(canonical_id)
        assert result is not None
        assert result.normalized_price_per_unit > 0
        assert result.normalized_unit == "g"
