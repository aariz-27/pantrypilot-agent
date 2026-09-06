from app.domain.grocery_models import ReferencePriceCandidate
from app.domain.reference_pricing import compute_reference_prices


def _candidate(price, unit_qty=500.0, source="Brand", product_name="Item", pkg_price=None):
    return ReferencePriceCandidate(
        normalized_price_per_unit=price,
        package_quantity=unit_qty,
        package_unit="g",
        package_price_aed=pkg_price if pkg_price is not None else round(price * unit_qty, 2),
        normalized_package_quantity=unit_qty,
        source_product_name=product_name,
        source_name=source,
        source_url=None,
    )


def test_single_contributor_uses_that_value():
    groups = {("tomato", "g"): [_candidate(0.02)]}
    results, incompatible = compute_reference_prices(groups)
    assert incompatible == []
    assert len(results) == 1
    assert results[0].normalized_price_per_unit == 0.02
    assert results[0].contributor_count == 1
    assert results[0].aggregation_basis == "median_single"


def test_odd_contributor_count_uses_middle_value():
    groups = {("tomato", "g"): [_candidate(0.01), _candidate(0.03), _candidate(0.05)]}
    results, _ = compute_reference_prices(groups)
    assert results[0].normalized_price_per_unit == 0.03
    assert results[0].aggregation_basis == "median_odd"


def test_even_contributor_count_uses_mean_of_middle_two():
    groups = {("tomato", "g"): [_candidate(0.01), _candidate(0.02), _candidate(0.03), _candidate(0.04)]}
    results, _ = compute_reference_prices(groups)
    assert results[0].normalized_price_per_unit == 0.025
    assert results[0].aggregation_basis == "median_even"


def test_multiple_brands_contribute_to_one_canonical_ingredient():
    groups = {
        ("cheddar_cheese", "g"): [
            _candidate(0.10, source="BrandA"),
            _candidate(0.12, source="BrandB"),
            _candidate(0.09, source="BrandC"),
        ]
    }
    results, _ = compute_reference_prices(groups)
    assert results[0].contributor_count == 3
    assert results[0].normalized_price_per_unit == 0.10


def test_incompatible_units_are_never_merged_and_are_reported():
    groups = {
        ("butter", "g"): [_candidate(0.05)],
        ("butter", "ml"): [_candidate(0.06)],
    }
    results, incompatible = compute_reference_prices(groups)
    assert results == []  # neither group promoted
    assert len(incompatible) == 1
    assert incompatible[0].canonical_id == "butter"
    assert set(incompatible[0].units_found) == {"g", "ml"}
    assert incompatible[0].contributor_count == 2


def test_compatible_and_incompatible_canonical_ids_do_not_interfere():
    groups = {
        ("butter", "g"): [_candidate(0.05)],
        ("butter", "ml"): [_candidate(0.06)],
        ("tomato", "g"): [_candidate(0.02), _candidate(0.03)],
    }
    results, incompatible = compute_reference_prices(groups)
    assert len(results) == 1
    assert results[0].canonical_id == "tomato"
    assert len(incompatible) == 1
    assert incompatible[0].canonical_id == "butter"


def test_representative_package_carried_through_for_cost_engine():
    groups = {("tomato", "g"): [_candidate(0.02, unit_qty=1000.0, pkg_price=20.0)]}
    results, _ = compute_reference_prices(groups)
    assert results[0].package_price_aed == 20.0
    assert results[0].normalized_package_quantity == 1000.0
