"""Module A (PP-001 deterministic core) + Module B (PP-002 provider
retrieval) integration validation.

Composes a provider-mapped Recipe (fetched through the real
RecipeAPIIOAdapter.get_details() public method, backed by a mocked
HTTP transport carrying a RecipeAPI.io-shaped fixture payload) through:

    provider mapping -> normalization -> pantry matching
    -> constraint evaluation -> ranking

using only PP-001's existing, unmodified deterministic functions and
PP-002's existing, unmodified provider code. No future agent or
end-to-end API is built here -- this is direct test composition only.

The fixture recipe below is clearly test-only data shaped like a real
RecipeAPI.io response; it is not bundled anywhere in production code
and is unreachable outside this test module.
"""

from __future__ import annotations

import httpx
import pytest

from app.config import Settings
from app.domain.candidate_evaluation import evaluate_candidate
from app.domain.ingredient_normalizer import normalize_ingredient_name, normalize_pantry
from app.domain.models import CostConfidence, CostEvaluation, Recipe, RejectionReason, UserConstraints
from app.domain.pantry_matcher import match_pantry
from app.domain.ranker import rank_candidates
from app.integrations.recipeapi_io import RecipeAPIIOAdapter

FAKE_KEY = "test-only-fake-key-not-a-real-secret"

# Clearly test-only fixture, shaped like a real RecipeAPI.io response
# (matches the field names observed against the live API during PP-002's
# smoke test). Never bundled in production code; only importable from
# this test module.
GOOD_MATCH_RECIPE_PAYLOAD = {
    "data": {
        "id": 501,
        "name": "Integration Test Chicken Rice",
        "cuisine": "asian",
        "meal_type": "main",
        "servings": 4,
        "prep_time": 10,
        "cook_time": 20,
        "instructions": ["Cook chicken.", "Cook rice.", "Combine with onion, garlic, and soy sauce."],
        "ingredients": [
            {"id": 1, "name": "chicken breast", "quantity": 2, "unit": "piece", "optional": False},
            {"id": 2, "name": "rice", "quantity": 2, "unit": "cup", "optional": False},
            {"id": 3, "name": "onion", "quantity": 1, "unit": "piece", "optional": False},
            {"id": 4, "name": "garlic", "quantity": 2, "unit": "clove", "optional": False},
            {"id": 5, "name": "soy sauce", "quantity": 2, "unit": "tbsp", "optional": False},
        ],
    }
}

UNKNOWN_INGREDIENT_RECIPE_PAYLOAD = {
    "data": {
        "id": 502,
        "name": "Integration Test Gochugaru Rice",
        "cuisine": "korean",
        "prep_time": 5,
        "cook_time": 15,
        "instructions": ["Cook rice.", "Season with gochugaru."],
        "ingredients": [
            {"id": 1, "name": "rice", "quantity": 1, "unit": "cup", "optional": False},
            {"id": 2, "name": "gochugaru", "quantity": 1, "unit": "tbsp", "optional": False},
        ],
    }
}


async def fetch_fixture_recipe(payload: dict) -> Recipe:
    """Fetches a fixture recipe through the real, unmodified
    RecipeAPIIOAdapter.get_details() public method -- this is genuine
    Module B code, not a shortcut around it."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url=RecipeAPIIOAdapter.BASE_URL)
    settings = Settings(_env_file=None, recipeapi_io_api_key=FAKE_KEY)
    async with RecipeAPIIOAdapter(settings, http_client=client) as adapter:
        return await adapter.get_details(str(payload["data"]["id"]))


def normalize_recipe(recipe: Recipe) -> Recipe:
    """The M08 normalization step a future Recipe Service/agent
    performs between fetching a Recipe (Module B) and evaluating it
    (Module A). Uses PP-001's unmodified normalize_ingredient_name()."""

    normalized_ingredients = []
    for ingredient in recipe.ingredients:
        result = normalize_ingredient_name(ingredient.raw_name)
        normalized_ingredients.append(
            ingredient.model_copy(update={"canonical_id": result.canonical_id, "normalization_status": result.status})
        )
    return recipe.model_copy(update={"ingredients": normalized_ingredients})


COMPLETE_COST = CostEvaluation(estimated_purchase_cost_aed=5.0, price_complete=True, cost_confidence=CostConfidence.HIGH)


# --- Scenario 1: good pantry match --------------------------------------------------


async def test_scenario_1_good_pantry_match_end_to_end():
    raw_recipe = await fetch_fixture_recipe(GOOD_MATCH_RECIPE_PAYLOAD)
    assert raw_recipe.provider == "recipeapi_io"
    assert raw_recipe.provider_recipe_id == "501"
    # Nothing invented: mapped fields trace directly to the fixture payload.
    assert raw_recipe.name == "Integration Test Chicken Rice"
    assert raw_recipe.prep_time_minutes == 10
    assert raw_recipe.cook_time_minutes == 20

    recipe = normalize_recipe(raw_recipe)
    pantry = normalize_pantry(["chicken breast", "rice", "onion", "garlic"])
    assert pantry.unresolved == ()  # all pantry terms resolve against the seed vocabulary

    pantry_match = match_pantry(pantry.canonical_ids, recipe.ingredients)
    assert pantry_match.pantry_coverage == pytest.approx(0.8)
    assert pantry_match.missing_ingredients == ("soy_sauce",)
    assert pantry_match.missing_count == 1

    constraints = UserConstraints(cuisine_preference="Asian")
    candidate = evaluate_candidate(recipe, pantry.canonical_ids, constraints, COMPLETE_COST)
    assert candidate.hard_constraint_pass is True

    [ranked] = rank_candidates(
        [candidate],
        constraints,
        recipe_cuisine_by_id={candidate.recipe_id: recipe.cuisine},
        recipe_name_by_id={candidate.recipe_id: recipe.name},
    )
    expected_score = 0.45 * 0.8 + 0.30 * 1.0 + 0.15 * (1 - 1 / 5) + 0.10 * 1.0
    assert ranked.deterministic_score == pytest.approx(expected_score)

    # Determinism: re-running the whole pipeline on the same inputs
    # produces an identical score, not just an identical ordering.
    candidate_again = evaluate_candidate(recipe, pantry.canonical_ids, constraints, COMPLETE_COST)
    [ranked_again] = rank_candidates(
        [candidate_again],
        constraints,
        recipe_cuisine_by_id={candidate_again.recipe_id: recipe.cuisine},
        recipe_name_by_id={candidate_again.recipe_id: recipe.name},
    )
    assert ranked_again.deterministic_score == ranked.deterministic_score


# --- Scenario 2: missing ingredients --------------------------------------------------


async def test_scenario_2_missing_ingredients_derived_correctly():
    recipe = normalize_recipe(await fetch_fixture_recipe(GOOD_MATCH_RECIPE_PAYLOAD))
    pantry = normalize_pantry(["rice", "onion"])

    pantry_match = match_pantry(pantry.canonical_ids, recipe.ingredients)
    assert pantry_match.pantry_coverage == pytest.approx(2 / 5)
    assert pantry_match.missing_count == 3
    assert pantry_match.missing_ingredients == ("chicken_breast", "garlic", "soy_sauce")


# --- Scenario 3: UNKNOWN required ingredient --------------------------------------------------


async def test_scenario_3_unknown_required_ingredient_reduces_coverage():
    recipe = normalize_recipe(await fetch_fixture_recipe(UNKNOWN_INGREDIENT_RECIPE_PAYLOAD))
    # Confirm the seed vocabulary genuinely doesn't resolve this ingredient
    # (a real integration finding, not assumed).
    gochugaru = next(i for i in recipe.ingredients if i.raw_name == "gochugaru")
    assert gochugaru.canonical_id is None

    pantry = normalize_pantry(["rice"])
    pantry_match = match_pantry(pantry.canonical_ids, recipe.ingredients)

    assert pantry_match.pantry_coverage == pytest.approx(0.5)  # 1 matched / (1 resolved + 1 unresolved)
    assert "gochugaru" in pantry_match.unresolved_ingredients
    assert "gochugaru" not in pantry_match.matched_ingredients
    assert "gochugaru" not in pantry_match.missing_ingredients  # canonical-only list, never raw names


# --- Scenario 4: exclusion --------------------------------------------------


async def test_scenario_4_excluded_ingredient_hard_rejected_before_ranking():
    recipe = normalize_recipe(await fetch_fixture_recipe(GOOD_MATCH_RECIPE_PAYLOAD))
    pantry = normalize_pantry(["chicken breast", "rice", "onion", "garlic"])
    constraints = UserConstraints(excluded_canonical=frozenset({"garlic"}))

    candidate = evaluate_candidate(recipe, pantry.canonical_ids, constraints, COMPLETE_COST)
    assert candidate.hard_constraint_pass is False
    assert RejectionReason.EXCLUDED_INGREDIENT_PRESENT in candidate.rejection_reasons

    # The ranker itself refuses to score a non-feasible candidate --
    # hard rejection happens before ranking, not as a side effect of it.
    from app.domain.errors import InvalidInputError

    with pytest.raises(InvalidInputError):
        rank_candidates([candidate], constraints, {}, {candidate.recipe_id: recipe.name})


# --- Scenario 5: strict cuisine --------------------------------------------------


async def test_scenario_5_strict_cuisine_mismatch_hard_rejected():
    recipe = normalize_recipe(await fetch_fixture_recipe(GOOD_MATCH_RECIPE_PAYLOAD))  # cuisine="asian"
    pantry = normalize_pantry(["chicken breast", "rice", "onion", "garlic"])
    constraints = UserConstraints(cuisine_preference="Italian", cuisine_strict=True)

    candidate = evaluate_candidate(recipe, pantry.canonical_ids, constraints, COMPLETE_COST)
    assert candidate.hard_constraint_pass is False
    assert RejectionReason.STRICT_CUISINE_MISMATCH in candidate.rejection_reasons


# --- Scenario 6: time constraint uses local prep+cook, never a provider field --------------------------------------------------


async def test_scenario_6_total_time_uses_local_prep_plus_cook():
    recipe = normalize_recipe(await fetch_fixture_recipe(GOOD_MATCH_RECIPE_PAYLOAD))
    assert recipe.prep_time_minutes == 10
    assert recipe.cook_time_minutes == 20
    # The Recipe DTO has no "max_prep_time" or "total_time" field at all --
    # architecturally, the constraint evaluator cannot substitute a
    # provider prep-time filter for the local total-time decision.
    assert not hasattr(recipe, "max_prep_time")
    assert not hasattr(recipe, "total_time_minutes")

    pantry = normalize_pantry(["chicken breast", "rice", "onion", "garlic"])

    too_strict = UserConstraints(max_total_time_minutes=25)  # 10+20=30 > 25
    candidate = evaluate_candidate(recipe, pantry.canonical_ids, too_strict, COMPLETE_COST)
    assert RejectionReason.MAX_TOTAL_TIME_EXCEEDED in candidate.rejection_reasons

    lenient = UserConstraints(max_total_time_minutes=45)  # 10+20=30 <= 45
    candidate_ok = evaluate_candidate(recipe, pantry.canonical_ids, lenient, COMPLETE_COST)
    assert RejectionReason.MAX_TOTAL_TIME_EXCEEDED not in candidate_ok.rejection_reasons


# --- Scenario 7: budget placeholder behavior (explicit CostEvaluation fixtures only) --------------------------------------------------


async def test_scenario_7_incomplete_cost_with_budget_is_indeterminate():
    recipe = normalize_recipe(await fetch_fixture_recipe(GOOD_MATCH_RECIPE_PAYLOAD))
    pantry = normalize_pantry(["chicken breast", "rice", "onion", "garlic"])
    constraints = UserConstraints(budget_aed=10.0)

    candidate = evaluate_candidate(recipe, pantry.canonical_ids, constraints, CostEvaluation.UNKNOWN)
    assert candidate.hard_constraint_pass is False
    assert RejectionReason.BUDGET_INDETERMINATE_COST_INCOMPLETE in candidate.rejection_reasons
    assert candidate.estimated_purchase_cost_aed is None  # never fabricated


async def test_scenario_7_known_cost_over_budget_is_rejected():
    recipe = normalize_recipe(await fetch_fixture_recipe(GOOD_MATCH_RECIPE_PAYLOAD))
    pantry = normalize_pantry(["chicken breast", "rice", "onion", "garlic"])
    constraints = UserConstraints(budget_aed=10.0)
    over_budget_cost = CostEvaluation(estimated_purchase_cost_aed=15.0, price_complete=True, cost_confidence=CostConfidence.HIGH)

    candidate = evaluate_candidate(recipe, pantry.canonical_ids, constraints, over_budget_cost)
    assert candidate.hard_constraint_pass is False
    assert RejectionReason.BUDGET_EXCEEDED in candidate.rejection_reasons


async def test_scenario_7_no_budget_incomplete_cost_uses_conservative_soft_score():
    recipe = normalize_recipe(await fetch_fixture_recipe(GOOD_MATCH_RECIPE_PAYLOAD))
    pantry = normalize_pantry(["chicken breast", "rice", "onion", "garlic"])
    constraints = UserConstraints(budget_aed=None)

    candidate = evaluate_candidate(recipe, pantry.canonical_ids, constraints, CostEvaluation.UNKNOWN)
    assert candidate.hard_constraint_pass is True  # no budget => incomplete cost is not a feasibility concern

    [ranked] = rank_candidates(
        [candidate], constraints, recipe_cuisine_by_id={}, recipe_name_by_id={candidate.recipe_id: recipe.name}
    )
    expected_score = 0.45 * 0.8 + 0.30 * 0.25 + 0.15 * (1 - 1 / 5) + 0.10 * 1.0
    assert ranked.deterministic_score == pytest.approx(expected_score)
