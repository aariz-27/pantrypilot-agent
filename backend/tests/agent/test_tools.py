"""Direct unit tests for app.agent.tools (M03 deterministic tool facade).

Focused regression coverage for the PR #15 Part 3 fix (2026-09-09): a
non-food "other requirement" ingredient (e.g. parchment paper) must never
contaminate cost/missing-ingredient computation, even though
app.domain.pantry_matcher already excluded it from ITS OWN
missing/coverage computation independently.
"""

from __future__ import annotations

from app.agent.tools import evaluate_recipe
from app.domain.models import RecipeIngredient, UserConstraints
from app.repositories.price_repository import PriceRepository

from .conftest import make_recipe


def test_non_food_other_requirement_never_contaminates_cost_completeness(price_db):
    recipe = make_recipe(
        ingredients=[
            RecipeIngredient(raw_name="tomato", raw_measure="100 g"),
            RecipeIngredient(raw_name="parchment paper", raw_measure="1 piece"),
        ]
    )
    result = evaluate_recipe(recipe, frozenset({"tomato"}), UserConstraints(), PriceRepository(price_db))

    # "tomato" is priced in the test fixture DB (see conftest.price_db) --
    # if the non-food item were incorrectly treated as an unpriced FOOD
    # ingredient, price_complete would be False and cost None here.
    assert result.price_complete is True
    assert result.estimated_purchase_cost_aed == 0.0  # tomato is in pantry; nothing food-related is missing
    assert "parchment_paper" not in result.missing_ingredients
    assert result.other_requirements == ["parchment_paper"]
    assert "parchment paper" not in result.unresolved_ingredients


def test_non_food_other_requirement_excluded_even_when_recipe_has_other_missing_food(price_db):
    recipe = make_recipe(
        ingredients=[
            RecipeIngredient(raw_name="onion", raw_measure="100 g"),
            RecipeIngredient(raw_name="cedar plank", raw_measure="1 piece"),
        ]
    )
    result = evaluate_recipe(recipe, frozenset(), UserConstraints(), PriceRepository(price_db))

    # "onion" IS priced and genuinely missing (empty pantry) -- cost
    # completeness must reflect only that real food gap, never the
    # cedar plank.
    assert result.price_complete is True
    assert result.estimated_purchase_cost_aed is not None and result.estimated_purchase_cost_aed > 0
    assert "cedar_plank" not in result.missing_ingredients
    assert "onion" in result.missing_ingredients
