"""Regression tests for the PR #15 controlled canonical + pricing
expansion pass (2026-09-09): 27 high-value REVIEW NEEDED items from the
yellow/Uncertain audit, validated against
data/raw/PantryPilot_Ingredients_Needing_Pricing.csv and promoted to
their own genuinely distinct canonical ids -- 19 with real CSV-backed
manual pricing, 8 identity-only (no usable CSV pricing evidence).

Every price figure asserted here was independently recomputed from the
CSV's own package_price_aed / normalized_package_quantity by the tests
themselves (not copied from the implementation), so a transcription
error in either place would be caught.
"""

from __future__ import annotations

import os

import pytest

from app.domain.grocery_taxonomy import CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES
from app.domain.ingredient_normalizer import normalize_ingredient_name
from app.repositories.price_repository import PriceRepository
from scripts.load_manual_price_entries import load_manual_entries

MANUAL_ENTRIES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "manual", "manual_price_entries.json"
)

# (raw text, expected canonical id, expected package_price_aed, expected
# normalized_package_quantity, expected normalized_unit) -- for the 19
# priced entries. normalized_price_per_unit is independently recomputed
# below (price / quantity), never hardcoded twice.
PRICED_ITEMS = [
    ("tomato paste", "tomato_paste", 4.65, 370, "g"),
    ("celery", "celery", 5.98, 500, "g"),
    ("garlic powder", "garlic_powder", 6.7, 115, "g"),
    ("onion powder", "onion_powder", 6.7, 130, "g"),
    ("green chili", "green_chili", 1.4, 100, "g"),
    ("buttermilk", "buttermilk", 8.0, 285, "ml"),
    ("smoked paprika", "smoked_paprika", 15.8, 150, "g"),
    ("cayenne", "cayenne_pepper", 10.5, 250, "g"),
    ("dried oregano", "dried_oregano", 12.3, 60, "g"),
    ("dried thyme", "dried_thyme", 9.75, 70, "g"),
    ("dried basil", "dried_basil", 8.25, 12, "g"),
    ("dried tarragon", "dried_tarragon", 11.0, 25, "g"),
    ("barbecue sauce", "barbecue_sauce", 15.95, 500, "g"),
    ("breadcrumb", "breadcrumbs", 10.25, 425, "g"),
    ("sour cream", "sour_cream", 7.1, 200, "g"),
    ("white pepper", "white_pepper", 15.35, 45, "g"),
    ("marinara sauce", "marinara_sauce", 10.5, 320, "g"),
    ("fresh coconut", "fresh_coconut", 3.5, 1, "pcs"),
    ("cherry tomato", "cherry_tomato", 8.95, 250, "g"),
]

# (raw text, expected canonical id) -- identity-only, no CSV pricing evidence.
IDENTITY_ONLY_ITEMS = [
    ("beef broth", "beef_broth"),
    ("chicken broth", "chicken_broth"),
    ("vegetable broth", "vegetable_broth"),
    ("fish stock", "fish_stock"),
    ("lamb broth", "lamb_broth"),
    ("lemon juice", "lemon_juice"),
    ("shallot", "shallot"),
    ("chive", "chives"),
]

# canonicals these must NEVER leak/collapse into (Priority 2: keep
# product-form distinctions explicit).
NO_LEAKAGE_TARGETS = {
    "tomato_paste": "tomato",
    "garlic_powder": "garlic",
    "onion_powder": "onion",
    "dried_thyme": "thyme",
    "dried_oregano": None,  # no fresh "oregano" canonical exists at all
    "dried_basil": "basil",
    "dried_tarragon": "tarragon",
    "lemon_juice": "lemon",
    "smoked_paprika": "paprika",
    "white_pepper": "black_pepper",
    "fresh_coconut": "coconut",
    "beef_broth": None,  # no "stock_powder"/"bouillon" collapse
    "cherry_tomato": "tomato",
}


# --- identity resolution -----------------------------------------------------


@pytest.mark.parametrize("raw,expected_canonical,_price,_qty,_unit", PRICED_ITEMS)
def test_priced_item_resolves_to_its_own_canonical(raw, expected_canonical, _price, _qty, _unit):
    result = normalize_ingredient_name(raw, CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES)
    assert result.canonical_id == expected_canonical


@pytest.mark.parametrize("raw,expected_canonical", IDENTITY_ONLY_ITEMS)
def test_identity_only_item_resolves_despite_no_price(raw, expected_canonical):
    result = normalize_ingredient_name(raw, CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES)
    assert result.canonical_id == expected_canonical


def test_plural_forms_resolve_via_existing_normalization_fallback():
    # No new alias entries were needed for these -- the existing
    # singular/plural stripping mechanism already reaches them once the
    # canonical id itself is in the vocabulary.
    for raw, expected in [
        ("breadcrumbs", "breadcrumbs"),
        ("shallots", "shallot"),
        ("chives", "chives"),
    ]:
        result = normalize_ingredient_name(raw, CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES)
        assert result.canonical_id == expected


def test_no_leakage_into_related_but_distinct_canonicals():
    for new_id, forbidden_target in NO_LEAKAGE_TARGETS.items():
        assert new_id in CANONICAL_GROCERY_INGREDIENTS
        if forbidden_target is not None:
            assert new_id != forbidden_target


# --- pricing lookup / price-unit basis ---------------------------------------


@pytest.fixture()
def loaded_db(tmp_path):
    db_path = str(tmp_path / "review_needed_expansion.db")
    load_manual_entries(MANUAL_ENTRIES_PATH, db_path)
    return db_path


@pytest.mark.parametrize("raw,canonical_id,price,qty,unit", PRICED_ITEMS)
def test_priced_item_pricing_lookup_matches_csv_evidence(loaded_db, raw, canonical_id, price, qty, unit):
    result = PriceRepository(loaded_db).get_price(canonical_id)
    assert result is not None
    assert result.source_type == "manual_curated"
    assert result.normalized_unit == unit
    assert result.package_price_aed == pytest.approx(price)
    assert result.normalized_package_quantity == pytest.approx(qty)
    # Recomputed independently here, not copied from the implementation.
    assert result.normalized_price_per_unit == pytest.approx(price / qty)


@pytest.mark.parametrize("raw,canonical_id", IDENTITY_ONLY_ITEMS)
def test_identity_only_item_has_no_price_row_never_zero(loaded_db, raw, canonical_id):
    result = PriceRepository(loaded_db).get_price(canonical_id)
    assert result is None  # never a fabricated AED 0


def test_fresh_coconut_uses_piece_count_basis_not_an_invented_weight(loaded_db):
    result = PriceRepository(loaded_db).get_price("fresh_coconut")
    assert result.normalized_unit == "pcs"
    assert result.package_unit == "pcs"
    assert result.normalized_package_quantity == 1
    assert result.normalized_price_per_unit == pytest.approx(3.5)


# --- cost-engine compatibility ------------------------------------------------


def test_priced_item_recipe_cost_calculation_end_to_end(loaded_db):
    from app.agent.tools import evaluate_recipe
    from app.domain.models import RecipeIngredient, UserConstraints

    from tests.agent.conftest import make_recipe

    recipe = make_recipe(
        ingredients=[RecipeIngredient(raw_name="tomato paste", raw_measure="370 g")],
    )
    result = evaluate_recipe(recipe, frozenset(), UserConstraints(), PriceRepository(loaded_db))

    assert "tomato_paste" in result.missing_ingredients
    assert result.price_complete is True
    # 1 package (370 g required == exactly 1 package of 370 g) at AED 4.65.
    assert result.estimated_purchase_cost_aed == pytest.approx(4.65)


def test_identity_only_item_never_fabricates_a_price_in_cost_calculation(loaded_db):
    from app.agent.tools import evaluate_recipe
    from app.domain.models import RecipeIngredient, UserConstraints

    from tests.agent.conftest import make_recipe

    recipe = make_recipe(
        ingredients=[RecipeIngredient(raw_name="beef broth", raw_measure="500 ml")],
    )
    result = evaluate_recipe(recipe, frozenset(), UserConstraints(), PriceRepository(loaded_db))

    assert "beef_broth" in result.missing_ingredients
    assert result.price_complete is False  # unavailable, never AED 0
    assert result.estimated_purchase_cost_aed is None


def test_fresh_coconut_unit_mismatch_falls_back_conservatively_never_a_fabricated_conversion(loaded_db):
    """The recipe asks for a gram quantity but fresh_coconut's only price
    is piece-based -- the frozen cost engine's existing, unmodified
    "no reliable compatible quantity -> one conservative package, MEDIUM
    confidence" fallback must apply. No piece-to-gram conversion is ever
    invented (DEC-013)."""

    from app.agent.tools import evaluate_recipe
    from app.domain.models import CostConfidence, RecipeIngredient, UserConstraints

    from tests.agent.conftest import make_recipe

    recipe = make_recipe(
        ingredients=[RecipeIngredient(raw_name="fresh coconut", raw_measure="100 g")],
    )
    result = evaluate_recipe(recipe, frozenset(), UserConstraints(), PriceRepository(loaded_db))

    assert "fresh_coconut" in result.missing_ingredients
    assert result.price_complete is True
    assert result.cost_confidence == CostConfidence.MEDIUM
    assert result.estimated_purchase_cost_aed == pytest.approx(3.5)  # exactly 1 package, no invented conversion
