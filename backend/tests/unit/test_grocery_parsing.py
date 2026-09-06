import pytest

from app.domain.grocery_models import PackageBasisSource
from app.domain.grocery_parsing import (
    clean_brand,
    parse_package_content,
    parse_price,
    resolve_canonical_id,
    validate_currency,
)
from app.domain.grocery_taxonomy import REFERENCE_PRICE_EXCLUDED_UNITS


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


def test_parse_malformed_range_content_never_fabricates_precision():
    # Independent review finding (2026-09-06): this real, malformed
    # scraper-artifact range must NOT resolve to its first number (1.2
    # kg) -- a range is always ambiguous, so it must stay fully
    # unresolved rather than silently accepting one endpoint.
    result = parse_package_content("1.2 kg-1.5 kg Appro x. Weight")
    assert result.normalized_unit is None
    assert result.normalized_total_quantity is None
    assert result.package_quantity is None


def test_parse_clean_range_content_stays_unresolved():
    # Real example from the Founder export: "Pineapple India 1 pc (1 kg - 1.3 kg)"
    result = parse_package_content("(1 kg - 1.3 kg)")
    assert result.normalized_unit is None
    assert result.normalized_total_quantity is None


def test_parse_additive_same_unit_bundle_totals_deterministically():
    # Real examples: "Sadia Frozen Tender Chicken Breast 2 kg + 1 kg",
    # "Al Baker All Purpose Flour No.1 2 kg + 1 kg" -- an unambiguous
    # same-dimension total, not a fabrication (both numbers are real).
    result = parse_package_content("2 kg + 1 kg")
    assert result.normalized_total_quantity == 3000
    assert result.normalized_unit == "g"


def test_parse_additive_bundle_mixed_mass_units_converts_and_sums():
    result = parse_package_content("900 g + 200 g")
    assert result.normalized_total_quantity == 1100
    assert result.normalized_unit == "g"

    # kg and g both normalize to the same base unit, so mixing them in
    # an additive bundle is still an unambiguous, correct total.
    result2 = parse_package_content("1 kg + 500 g")
    assert result2.normalized_total_quantity == 1500
    assert result2.normalized_unit == "g"


def test_parse_additive_bundle_incompatible_dimensions_stays_unresolved():
    # Defensive: a "+" bundle spanning two different dimensions must
    # never be guessed at.
    result = parse_package_content("2 kg + 3 pcs")
    assert result.normalized_unit is None
    assert result.normalized_total_quantity is None


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


def test_resolve_canonical_id_keyword_family_with_no_evidence_is_unmapped_not_guessed():
    # Independent review (2026-09-06): a family productType whose title
    # carries no distinguishing keyword must be UNMAPPED, never defaulted
    # to a guessed "standard" variant (DEC-013's uncertain-mappings-stay-
    # unresolved rule).
    assert resolve_canonical_id("Fresh Milk", "Some Brand Fresh Milk 1 L") is None
    assert resolve_canonical_id("Flour", "Some Brand Flour 1 kg") is None
    assert resolve_canonical_id("Peas & Beans", "Some Brand Mixed 500 g") is None


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


# --- independent review regression tests (2026-09-06) -------------------------------


def test_sweet_potato_never_maps_to_generic_potato():
    # Finding 4: "potato" is a substring of "sweet potato"; the more
    # specific phrase must be checked first.
    assert resolve_canonical_id("Potatoes & Starchy Vegetables", "Sweet Potato Egypt 500 g") == "sweet_potato"
    assert resolve_canonical_id("Potatoes & Starchy Vegetables", "Potato Lebanon 1 kg") == "potato"


def test_moong_dal_never_maps_to_generic_lentils():
    # Finding 4: "dal" is a substring of "moong dal"/"chana dal"/"toor
    # dal"/"urid dal"; each specific phrase must be checked before the
    # generic "dal" fallback.
    assert resolve_canonical_id("Pulses", "LuLu Moong Dal 800 g") == "moong_dal"
    assert resolve_canonical_id("Pulses", "LuLu Chana Dal 800 g") == "chana_dal"
    assert resolve_canonical_id("Pulses", "Bayara Toor Dal 400 g") == "toor_dal"
    assert resolve_canonical_id("Pulses", "Bayara Urid Dal 400 g") == "urad_dal"
    assert resolve_canonical_id("Pulses", "LuLu Masoor Dal 800 g") == "lentils"


def test_feta_white_cheese_product_type_is_not_treated_as_universally_feta():
    # Finding 2: real example -- "Puck Cream Cheese Spread 300 g" carries
    # productType "Feta & White Cheese" in the actual export.
    assert resolve_canonical_id("Feta & White Cheese", "Puck Cream Cheese Spread 300 g") == "cream_cheese"
    assert resolve_canonical_id("Feta & White Cheese", "Almarai Full Fat Feta Cheese 200 g") == "feta_cheese"
    assert resolve_canonical_id("Feta & White Cheese", "Puck Halloumi Cheese 200 g") == "halloumi_cheese"
    assert resolve_canonical_id("Feta & White Cheese", "Belgioioso Mascarpone Creamy Spreadable Cheese 226 g") == "mascarpone_cheese"
    # A title with no specific cheese-type keyword is UNMAPPED, not
    # guessed as feta merely because of the productType label.
    assert resolve_canonical_id("Feta & White Cheese", "Muratbey Anatolian Mix Cheese 200 g") is None


def test_mozzarella_and_other_grated_cheese_disambiguates_by_title():
    # Finding 2: this productType genuinely contains Parmesan, Cheddar,
    # and mixed blends in the real export, not just mozzarella.
    assert resolve_canonical_id("Mozzarella & Other Grated Cheese", "The Three Cows Shredded Mozzarella Cheese 200 g") == "mozzarella_cheese"
    assert resolve_canonical_id("Mozzarella & Other Grated Cheese", "Crystal Farms Parmesan Cheese 226 g") == "parmesan_cheese"
    assert resolve_canonical_id("Mozzarella & Other Grated Cheese", "President Shredded Cheddar Cheese 200 g") == "cheddar_cheese"
    assert resolve_canonical_id("Mozzarella & Other Grated Cheese", "Sargento Off The Block Traditional Cut 4 Cheese Mexican 226 g") == "mixed_shredded_cheese"


def test_ginger_stays_taxonomy_unmapped_from_lulu_despite_manual_gap_fill():
    # Essential-ingredient audit (2026-09-06): "ginger" is registered as a
    # recognized canonical ID (see grocery_taxonomy.MANUAL_ONLY_CANONICAL_
    # INGREDIENTS) so a Founder-reviewed manual price entry can exist for
    # it, but this must NOT make real LuLu ingestion suddenly map ginger
    # products -- there is still no productType rule for "Chillies &
    # Spicy", so ingestion-time resolution is unchanged.
    assert resolve_canonical_id("Chillies & Spicy", "Ginger India 200 g") is None
    assert resolve_canonical_id("Chillies & Spicy", "Ginger China 250 g") is None


def test_generic_butter_productype_mapping_unaffected_by_salted_unsalted_addition():
    # Registering salted_butter/unsalted_butter as recognized canonical
    # IDs must not change how real LuLu "Butter" productType titles
    # ingest -- productType "Butter" remains fixed-mapped to generic
    # "butter" for both salted and unsalted real titles (Founder decision:
    # do not repurpose or re-split generic butter in this ticket).
    assert resolve_canonical_id("Butter", "Lurpak Butter Block Salted 400 g") == "butter"
    assert resolve_canonical_id("Butter", "Almarai Unsalted Natural Butter 200 g") == "butter"


def test_carrots_producttype_maps_to_canonical_carrot():
    # Essential-ingredient data-quality fix (2026-09-06): real productType
    # "Carrots" had no mapping rule at all -- narrow fixed mapping added.
    assert resolve_canonical_id("Carrots", "Carrots Australia 500 g") == "carrot"
    assert resolve_canonical_id("Carrots", "Fresh Carrots 1 kg") == "carrot"


def test_shredded_coconut_splits_from_whole_coconut():
    # Final Module C pricing-gap resolution (2026-09-06): a processed,
    # mass-based shredded/desiccated coconut has materially different
    # recipe intent from a whole fresh coconut -- the fixed-canonical
    # override splits it into its own canonical_id, while every other
    # real "Coconut" title (no "shredded"/"desiccated" keyword) keeps
    # resolving to the existing default, "coconut", unchanged.
    assert resolve_canonical_id("Coconut", "Coconut Shredded India 350 g") == "shredded_coconut"
    assert resolve_canonical_id("Coconut", "Coconut Whole India 1 pc") == "coconut"
    assert resolve_canonical_id("Coconut", "King Coconut 1 pc") == "coconut"
    assert resolve_canonical_id("Coconut", "Tender Coconut Thailand 1 pc") == "coconut"
    assert resolve_canonical_id("Coconut", "Tender Coconut with Opener 1 pc") == "coconut"


def test_reference_price_excluded_units_is_narrowly_scoped():
    # Essential-ingredient / final Module C pricing-gap resolution
    # (2026-09-06): the exclusion table must remain exactly as narrow as
    # the real evidence justifies for each canonical_id, never a blanket
    # rule and never applied to an unrelated canonical_id such as "egg"
    # (which is correctly pcs-based).
    assert REFERENCE_PRICE_EXCLUDED_UNITS == {
        "butter": frozenset({"ml"}),
        "apple": frozenset({"pcs"}),
        "evaporated_milk": frozenset({"ml"}),
        "flavoured_yoghurt": frozenset({"ml", "pcs"}),
        "fresh_cream": frozenset({"ml"}),
        "ghee": frozenset({"g"}),
        "ketchup": frozenset({"ml"}),
        "whipping_cream": frozenset({"g"}),
    }
    assert "egg" not in REFERENCE_PRICE_EXCLUDED_UNITS
    assert "corn" not in REFERENCE_PRICE_EXCLUDED_UNITS
    assert "mayonnaise" not in REFERENCE_PRICE_EXCLUDED_UNITS


def test_speciality_cheese_never_counts_a_non_cheese_dip_as_cheese():
    # Finding 1+2 combined: "Moutabal" (an eggplant dip) genuinely
    # appears under productType "Speciality Cheese" in the real export.
    # With no default, it correctly falls through to UNMAPPED.
    assert resolve_canonical_id("Speciality Cheese", "Smart Gourmet Classic Moutabal 200 g") is None
    assert resolve_canonical_id("Speciality Cheese", "Fresh Labneh With Zaatar 250 g") == "labneh"
    assert resolve_canonical_id("Speciality Cheese", "Dutch Gouda Mild Cheese 250 g") == "gouda_cheese"
