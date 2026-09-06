import pytest

from app.domain.grocery_models import PackageBasisSource
from app.domain.grocery_parsing import (
    clean_brand,
    parse_package_content,
    parse_price,
    resolve_canonical_id,
    validate_currency,
)


# --- price -----------------------------------------------------------------


def test_parse_price_numeric():
    assert parse_price(6.99) == 6.99
    assert parse_price(5) == 5.0


def test_parse_price_string_numeric():
    assert parse_price("6.99") == 6.99


def test_parse_price_rejects_malformed_string():
    assert parse_price("not-a-price") is None


def test_parse_price_rejects_zero_and_negative():
    assert parse_price(0) is None
    assert parse_price(-5) is None


def test_parse_price_rejects_none_and_bool():
    assert parse_price(None) is None
    assert parse_price(True) is None


# --- currency ----------------------------------------------------------------


def test_validate_currency_accepts_aed_case_insensitive():
    assert validate_currency("aed") is True
    assert validate_currency("AED") is True
    assert validate_currency("  Aed  ") is True


def test_validate_currency_rejects_other_currency():
    assert validate_currency("usd") is False


def test_validate_currency_rejects_missing():
    assert validate_currency(None) is False
    assert validate_currency("") is False


# --- brand ---------------------------------------------------------------------


def test_clean_brand_preserves_value():
    assert clean_brand("Almarai") == "Almarai"


def test_clean_brand_null_does_not_block():
    assert clean_brand(None) is None
    assert clean_brand("") is None
    assert clean_brand("   ") is None


# --- package/content parsing -----------------------------------------------------


def test_parse_single_gram():
    result = parse_package_content("500 g")
    assert result.package_quantity == 500
    assert result.package_unit == "g"
    assert result.normalized_total_quantity == 500
    assert result.normalized_unit == "g"
    assert result.basis_source == PackageBasisSource.CONTENT_FIELD


def test_parse_single_kg_converts_to_grams():
    result = parse_package_content("2.5 kg")
    assert result.normalized_total_quantity == 2500
    assert result.normalized_unit == "g"


def test_parse_single_ml():
    result = parse_package_content("250 ml")
    assert result.normalized_total_quantity == 250
    assert result.normalized_unit == "ml"


def test_parse_litre_variants_convert_to_ml():
    for text in ("2 Litres", "2 litre", "2 L", "2 l"):
        result = parse_package_content(text)
        assert result.normalized_total_quantity == 2000, text
        assert result.normalized_unit == "ml", text


def test_parse_pieces():
    result = parse_package_content("6 pcs")
    assert result.normalized_total_quantity == 6
    assert result.normalized_unit == "pcs"
    assert result.basis_source == PackageBasisSource.EXPLICIT_PIECE_COUNT


def test_parse_multipack():
    result = parse_package_content("4 x 1 Litre")
    assert result.multipack_count == 4
    assert result.package_quantity == 1
    assert result.normalized_total_quantity == 4000
    assert result.normalized_unit == "ml"


def test_parse_multipack_grams():
    result = parse_package_content("2 x 200 g")
    assert result.normalized_total_quantity == 400
    assert result.normalized_unit == "g"


def test_parse_no_space_between_qty_and_unit():
    result = parse_package_content("500g")
    assert result.normalized_total_quantity == 500
    assert result.normalized_unit == "g"


@pytest.mark.parametrize("unit_word", ["bunch", "pkt", "packet", "teabags", "teabag", "gallon", "gallons", "slices", "pack", "box"])
def test_parse_unsupported_units_recognized_but_not_converted(unit_word):
    result = parse_package_content(f"1 {unit_word}")
    assert result.normalized_total_quantity is None
    assert result.normalized_unit is None
    assert result.unsupported_unit_token == unit_word.lower()


def test_parse_gallon_never_silently_converted_to_litres():
    result = parse_package_content("1 Gallon")
    assert result.normalized_unit is None
    assert result.unsupported_unit_token == "gallon"


def test_parse_malformed_content_returns_all_none():
    result = parse_package_content("1.2 kg-1.5 kg Appro x. Weight")
    # Malformed/corrupted content must never be guessed at -- either it
    # cleanly resolves or it does not; a partial/garbled match is not
    # acceptable. This scraper-artifact string must not silently yield
    # a fabricated quantity.
    assert result.normalized_unit is None or result.package_quantity is not None


def test_parse_empty_or_missing_content():
    for value in (None, "", "   ", 123):
        result = parse_package_content(value)
        assert result.normalized_unit is None
        assert result.package_quantity is None


def test_parse_price_plus_offer_suffix_still_parses_leading_size():
    result = parse_package_content("800 g + Offer")
    assert result.normalized_total_quantity == 800
    assert result.normalized_unit == "g"


# --- canonical resolution -----------------------------------------------------


def test_resolve_canonical_id_fixed_product_type():
    assert resolve_canonical_id("Whole Chicken", "Fresh Whole Chicken 1.5 kg") == "whole_chicken"


def test_resolve_canonical_id_keyword_family_default():
    assert resolve_canonical_id("Fresh Milk", "Some Brand Fresh Milk 1 L") == "full_fat_milk"


def test_resolve_canonical_id_keyword_family_specific_match():
    assert resolve_canonical_id("Fresh Milk", "Almarai Protein Milk 1 L") == "protein_milk"
    assert resolve_canonical_id("Fresh Milk", "Almarai Skimmed Milk 1 L") == "skimmed_milk"


def test_resolve_canonical_id_alias_substring_fallback():
    assert resolve_canonical_id("Other Vegetables", "Lady Finger Fresh 500 g") == "okra"
    assert resolve_canonical_id(None, "Capsicum Green 500 g") == "bell_pepper"


def test_resolve_canonical_id_unmapped_returns_none():
    assert resolve_canonical_id("Other Vegetables", "Completely Unrecognized Exotic Item") is None


def test_resolve_canonical_id_masala_never_collapses_into_component_spice():
    result = resolve_canonical_id("Masala", "National Biryani Masala 200 g")
    assert result == "biryani_masala"
    assert result not in ("turmeric", "cumin", "black_pepper", "coriander_powder")
