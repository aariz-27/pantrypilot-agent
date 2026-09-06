"""Module A + B + C integration validation:

    recipe ingredient -> normalization -> canonical ID -> pantry matching
    -> price lookup -> cost -> constraints -> ranking

using the real CostEngine/PriceRepository (Module C) instead of hand-built
CostEvaluation fixtures, proving the pricing layer plugs into PP-001's
frozen constraint evaluator/ranker without any change to those contracts.
No LLM required anywhere in this chain.
"""

import pytest

from app.db.connection import connection_scope
from app.db.schema import create_schema
from app.domain.cost_engine import estimate_purchase_cost
from app.domain.grocery_taxonomy import CANONICAL_GROCERY_INGREDIENTS, GROCERY_INGREDIENT_ALIASES
from app.domain.ingredient_normalizer import normalize_ingredient_name, normalize_pantry
from app.domain.models import NormalizationStatus, Recipe, RecipeIngredient, RejectionReason, UserConstraints
from app.domain.pantry_matcher import match_pantry
from app.domain.candidate_evaluation import evaluate_candidate
from app.domain.ranker import rank_candidates
from app.repositories.price_repository import PriceRepository


@pytest.fixture()
def price_db(tmp_path):
    path = str(tmp_path / "abc_integration.db")
    with connection_scope(path, read_only=False) as connection:
        create_schema(connection)
        rows = [
            ("tomato", "g", "tomato", 0.02, 1000, "g", 20.0, 1000, 2, "median_even",
             "lulu_uae", "Tomato 1 kg", "https://example.test/tomato", "2026-09-06"),
            ("onion", "g", "onion", 0.005, 1000, "g", 5.0, 1000, 2, "median_even",
             "lulu_uae", "Onion 1 kg", "https://example.test/onion", "2026-09-06"),
            ("garlic", "g", "garlic", 0.015, 200, "g", 3.0, 200, 1, "median_single",
             "lulu_uae", "Garlic 200 g", "https://example.test/garlic", "2026-09-06"),
        ]
        connection.executemany(
            """
            INSERT INTO ingredient_prices (
                canonical_id, normalized_unit, display_name, normalized_price_per_unit,
                package_quantity, package_unit, package_price_aed, normalized_package_quantity,
                contributor_count, aggregation_basis, source_name, source_product_name,
                source_url, collected_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        connection.commit()
    return path


def normalize_recipe_ingredients(recipe: Recipe) -> Recipe:
    """The M08 normalization step, using the grocery taxonomy's
    vocabulary so recipe-side canonical IDs correlate with the pricing
    layer's -- proving the unified canonical namespace design."""
    normalized = []
    for ing in recipe.ingredients:
        result = normalize_ingredient_name(
            ing.raw_name, canonical_vocabulary=CANONICAL_GROCERY_INGREDIENTS, aliases=GROCERY_INGREDIENT_ALIASES
        )
        normalized.append(
            ing.model_copy(update={"canonical_id": result.canonical_id, "normalization_status": result.status})
        )
    return recipe.model_copy(update={"ingredients": normalized})


def make_recipe(**overrides) -> Recipe:
    defaults = dict(
        id="lulu_test_recipe:1",
        provider="test_provider",
        provider_recipe_id="1",
        name="Test Tomato Onion Garlic Dish",
        cuisine="Test Cuisine",
        ingredients=[
            RecipeIngredient(raw_name="tomato", raw_measure="500 g"),
            RecipeIngredient(raw_name="onion", raw_measure="200 g"),
            RecipeIngredient(raw_name="garlic", raw_measure="50 g"),
        ],
        instructions="Chop and cook everything together.",
    )
    defaults.update(overrides)
    return Recipe(**defaults)


def test_full_chain_good_match_with_real_cost(price_db):
    repo = PriceRepository(price_db)
    recipe = normalize_recipe_ingredients(make_recipe())
    pantry = normalize_pantry(["tomato", "onion"], canonical_vocabulary=CANONICAL_GROCERY_INGREDIENTS, aliases=GROCERY_INGREDIENT_ALIASES)

    pantry_match = match_pantry(pantry.canonical_ids, recipe.ingredients)
    assert pantry_match.missing_ingredients == ("garlic",)
    assert pantry_match.pantry_coverage == pytest.approx(2 / 3)

    missing_ingredients = [ing for ing in recipe.ingredients if ing.canonical_id in pantry_match.missing_ingredients]
    cost = estimate_purchase_cost(missing_ingredients, repo)
    assert cost.price_complete is True
    assert cost.estimated_purchase_cost_aed == 3.0  # one 200g garlic package covers the 50g requirement

    constraints = UserConstraints(budget_aed=10.0)
    candidate = evaluate_candidate(recipe, pantry.canonical_ids, constraints, cost)
    assert candidate.hard_constraint_pass is True

    [ranked] = rank_candidates(
        [candidate], constraints, recipe_cuisine_by_id={candidate.recipe_id: recipe.cuisine},
        recipe_name_by_id={candidate.recipe_id: recipe.name},
    )
    assert ranked.deterministic_score is not None
    assert 0.0 <= ranked.deterministic_score <= 1.0


def test_full_chain_unresolved_ingredient_reduces_coverage_without_fabricating_cost(price_db):
    repo = PriceRepository(price_db)
    recipe = normalize_recipe_ingredients(
        make_recipe(
            ingredients=[
                RecipeIngredient(raw_name="tomato", raw_measure="500 g"),
                RecipeIngredient(raw_name="saffron", raw_measure="1 g"),  # not in the grocery taxonomy at all
            ]
        )
    )
    pantry = normalize_pantry(["tomato"], canonical_vocabulary=CANONICAL_GROCERY_INGREDIENTS, aliases=GROCERY_INGREDIENT_ALIASES)

    # saffron has no canonical identity (UNKNOWN) -- it can never be
    # priced or fabricated a canonical ID. Its uncertainty shows up as
    # reduced pantry coverage (PP-001's existing UNKNOWN-reduces-
    # coverage rule), not as a fabricated cost line for an ingredient
    # we cannot even identify.
    pantry_match = match_pantry(pantry.canonical_ids, recipe.ingredients)
    assert "saffron" in pantry_match.unresolved_ingredients
    assert pantry_match.pantry_coverage < 1.0

    missing_with_canonical_id = [
        ing for ing in recipe.ingredients if ing.canonical_id and ing.canonical_id in pantry_match.missing_ingredients
    ]
    cost = estimate_purchase_cost(missing_with_canonical_id, repo)

    constraints = UserConstraints(budget_aed=10.0)
    candidate = evaluate_candidate(recipe, pantry.canonical_ids, constraints, cost)

    # No fabricated price anywhere: tomato is pantry-present (matched,
    # not costed) and saffron has no identity to cost at all, so the
    # complete-but-zero cost here reflects "nothing identifiable needed
    # buying" -- not a false claim that the recipe is fully known. The
    # reduced coverage is what carries the actual uncertainty signal.
    assert candidate.pantry_coverage < 1.0
    assert candidate.price_complete is True
    assert candidate.estimated_purchase_cost_aed == 0.0


def test_full_chain_ranking_is_deterministic_across_runs(price_db):
    repo = PriceRepository(price_db)
    recipe = normalize_recipe_ingredients(make_recipe())
    pantry = normalize_pantry(["tomato", "onion"], canonical_vocabulary=CANONICAL_GROCERY_INGREDIENTS, aliases=GROCERY_INGREDIENT_ALIASES)
    pantry_match = match_pantry(pantry.canonical_ids, recipe.ingredients)
    missing_ingredients = [ing for ing in recipe.ingredients if ing.canonical_id in pantry_match.missing_ingredients]

    constraints = UserConstraints(budget_aed=10.0)

    scores = []
    for _ in range(2):
        cost = estimate_purchase_cost(missing_ingredients, repo)
        candidate = evaluate_candidate(recipe, pantry.canonical_ids, constraints, cost)
        [ranked] = rank_candidates(
            [candidate], constraints, recipe_cuisine_by_id={}, recipe_name_by_id={candidate.recipe_id: recipe.name}
        )
        scores.append(ranked.deterministic_score)

    assert scores[0] == scores[1]


def test_full_chain_excluded_ingredient_still_hard_rejects_before_pricing(price_db):
    repo = PriceRepository(price_db)
    recipe = normalize_recipe_ingredients(make_recipe())
    pantry = normalize_pantry(["tomato", "onion", "garlic"], canonical_vocabulary=CANONICAL_GROCERY_INGREDIENTS, aliases=GROCERY_INGREDIENT_ALIASES)
    pantry_match = match_pantry(pantry.canonical_ids, recipe.ingredients)
    missing_ingredients = [ing for ing in recipe.ingredients if ing.canonical_id in pantry_match.missing_ingredients]
    cost = estimate_purchase_cost(missing_ingredients, repo)  # complete, cost=0.0 (nothing missing)

    constraints = UserConstraints(excluded_canonical=frozenset({"garlic"}))
    candidate = evaluate_candidate(recipe, pantry.canonical_ids, constraints, cost)
    assert candidate.hard_constraint_pass is False
    assert RejectionReason.EXCLUDED_INGREDIENT_PRESENT in candidate.rejection_reasons
