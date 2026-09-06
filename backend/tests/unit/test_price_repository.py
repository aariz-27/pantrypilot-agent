import pytest

from app.db.connection import connection_scope
from app.db.schema import create_schema
from app.repositories.price_repository import PriceRepository


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
