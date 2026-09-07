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


# --- additional full-pipeline scenarios (pre-Module-D audit, 2026-09-07) ----
#
# Module D (agent orchestration) and the /api/recommend endpoint do not
# exist yet, so these scenarios are exercised at the lowest existing
# integration boundary: the same normalize -> match -> price -> cost ->
# constrain -> rank chain the tests above already prove, using the real
# CostEngine/PriceRepository. Provider-layer scenarios (malformed/empty/
# timeout responses) are intentionally NOT repeated here -- they are
# already covered at their correct boundary in
# tests/unit/test_recipeapi_io_adapter.py. Ranking tie-break determinism
# is already covered directly in tests/unit/test_ranker.py against
# hand-built CandidateEvaluation objects, which is the right boundary
# for that concern.


def test_pantry_already_contains_every_recipe_ingredient(price_db):
    repo = PriceRepository(price_db)
    recipe = normalize_recipe_ingredients(make_recipe())
    pantry = normalize_pantry(
        ["tomato", "onion", "garlic"], canonical_vocabulary=CANONICAL_GROCERY_INGREDIENTS, aliases=GROCERY_INGREDIENT_ALIASES
    )
    pantry_match = match_pantry(pantry.canonical_ids, recipe.ingredients)
    assert pantry_match.missing_ingredients == ()
    assert pantry_match.pantry_coverage == 1.0

    cost = estimate_purchase_cost([], repo)
    assert cost.estimated_purchase_cost_aed == 0.0
    assert cost.price_complete is True

    candidate = evaluate_candidate(recipe, pantry.canonical_ids, UserConstraints(budget_aed=0.0), cost)
    assert candidate.hard_constraint_pass is True
    assert candidate.missing_count == 0


def test_missing_ingredient_with_resolved_canonical_id_but_no_price_is_incomplete_never_zero(price_db):
    # Distinct from the "unresolved ingredient" (saffron/UNKNOWN) case
    # above: here the ingredient normalizes to a real, known canonical
    # ID ("ginger") that simply has no row in this price database --
    # the cost must still be incomplete, never a fabricated zero.
    repo = PriceRepository(price_db)
    recipe = normalize_recipe_ingredients(
        make_recipe(
            ingredients=[
                RecipeIngredient(raw_name="tomato", raw_measure="500 g"),
                RecipeIngredient(raw_name="ginger", raw_measure="10 g"),
            ]
        )
    )
    assert recipe.ingredients[1].canonical_id == "ginger"  # resolved, not UNKNOWN

    pantry = normalize_pantry([], canonical_vocabulary=CANONICAL_GROCERY_INGREDIENTS, aliases=GROCERY_INGREDIENT_ALIASES)
    pantry_match = match_pantry(pantry.canonical_ids, recipe.ingredients)
    assert "ginger" in pantry_match.missing_ingredients

    missing_ingredients = [ing for ing in recipe.ingredients if ing.canonical_id in pantry_match.missing_ingredients]
    cost = estimate_purchase_cost(missing_ingredients, repo)
    assert cost.price_complete is False
    assert cost.estimated_purchase_cost_aed is None

    constraints = UserConstraints(budget_aed=10.0)
    candidate = evaluate_candidate(recipe, pantry.canonical_ids, constraints, cost)
    assert candidate.hard_constraint_pass is False
    assert RejectionReason.BUDGET_INDETERMINATE_COST_INCOMPLETE in candidate.rejection_reasons
    assert candidate.estimated_purchase_cost_aed is None


def test_budget_exactly_equals_estimated_cost_passes(price_db):
    repo = PriceRepository(price_db)
    recipe = normalize_recipe_ingredients(make_recipe())
    pantry = normalize_pantry(["tomato", "onion"], canonical_vocabulary=CANONICAL_GROCERY_INGREDIENTS, aliases=GROCERY_INGREDIENT_ALIASES)
    pantry_match = match_pantry(pantry.canonical_ids, recipe.ingredients)
    missing_ingredients = [ing for ing in recipe.ingredients if ing.canonical_id in pantry_match.missing_ingredients]
    cost = estimate_purchase_cost(missing_ingredients, repo)
    assert cost.estimated_purchase_cost_aed == 3.0  # one 200g garlic package

    candidate = evaluate_candidate(recipe, pantry.canonical_ids, UserConstraints(budget_aed=3.0), cost)
    assert candidate.hard_constraint_pass is True
    assert RejectionReason.BUDGET_EXCEEDED not in candidate.rejection_reasons


def test_estimated_cost_exceeding_budget_hard_rejects_through_full_chain(price_db):
    repo = PriceRepository(price_db)
    recipe = normalize_recipe_ingredients(make_recipe())
    pantry = normalize_pantry(["onion"], canonical_vocabulary=CANONICAL_GROCERY_INGREDIENTS, aliases=GROCERY_INGREDIENT_ALIASES)
    pantry_match = match_pantry(pantry.canonical_ids, recipe.ingredients)
    missing_ingredients = [ing for ing in recipe.ingredients if ing.canonical_id in pantry_match.missing_ingredients]
    cost = estimate_purchase_cost(missing_ingredients, repo)  # tomato (20 AED) + garlic (3 AED) = 23 AED

    candidate = evaluate_candidate(recipe, pantry.canonical_ids, UserConstraints(budget_aed=10.0), cost)
    assert candidate.hard_constraint_pass is False
    assert RejectionReason.BUDGET_EXCEEDED in candidate.rejection_reasons


def test_recipe_exceeding_max_total_time_hard_rejects(price_db):
    repo = PriceRepository(price_db)
    recipe = normalize_recipe_ingredients(make_recipe(prep_time_minutes=20, cook_time_minutes=50))
    pantry = normalize_pantry(
        ["tomato", "onion", "garlic"], canonical_vocabulary=CANONICAL_GROCERY_INGREDIENTS, aliases=GROCERY_INGREDIENT_ALIASES
    )
    pantry_match = match_pantry(pantry.canonical_ids, recipe.ingredients)
    cost = estimate_purchase_cost([], repo)

    constraints = UserConstraints(max_total_time_minutes=60)  # prep(20) + cook(50) = 70 > 60
    candidate = evaluate_candidate(recipe, pantry.canonical_ids, constraints, cost)
    assert candidate.hard_constraint_pass is False
    assert RejectionReason.MAX_TOTAL_TIME_EXCEEDED in candidate.rejection_reasons
    assert pantry_match.pantry_coverage == 1.0  # time rejection is independent of pantry match


def test_cuisine_strict_match_succeeds(price_db):
    repo = PriceRepository(price_db)
    recipe = normalize_recipe_ingredients(make_recipe(cuisine="Pakistani"))
    pantry = normalize_pantry(
        ["tomato", "onion", "garlic"], canonical_vocabulary=CANONICAL_GROCERY_INGREDIENTS, aliases=GROCERY_INGREDIENT_ALIASES
    )
    cost = estimate_purchase_cost([], repo)
    constraints = UserConstraints(cuisine_preference="Pakistani", cuisine_strict=True)
    candidate = evaluate_candidate(recipe, pantry.canonical_ids, constraints, cost)
    assert candidate.hard_constraint_pass is True
    assert candidate.cuisine_match is True


def test_cuisine_strict_mismatch_hard_rejects(price_db):
    repo = PriceRepository(price_db)
    recipe = normalize_recipe_ingredients(make_recipe(cuisine="Italian"))
    pantry = normalize_pantry(
        ["tomato", "onion", "garlic"], canonical_vocabulary=CANONICAL_GROCERY_INGREDIENTS, aliases=GROCERY_INGREDIENT_ALIASES
    )
    cost = estimate_purchase_cost([], repo)
    constraints = UserConstraints(cuisine_preference="Pakistani", cuisine_strict=True)
    candidate = evaluate_candidate(recipe, pantry.canonical_ids, constraints, cost)
    assert candidate.hard_constraint_pass is False
    assert RejectionReason.STRICT_CUISINE_MISMATCH in candidate.rejection_reasons
    assert candidate.cuisine_match is False


def test_duplicate_and_aliased_ingredient_names_normalize_to_one_canonical_id(price_db):
    # "Onions" (plural) and "onion" (exact) must both resolve to the
    # same canonical ID and collapse into a single pantry entry, per
    # M08's dedup rule -- proven here through the real normalizer, not
    # a hand-set canonical_id.
    pantry = normalize_pantry(
        ["Onions", "onion", "  Onion  "], canonical_vocabulary=CANONICAL_GROCERY_INGREDIENTS, aliases=GROCERY_INGREDIENT_ALIASES
    )
    assert pantry.canonical_ids == frozenset({"onion"})
    assert pantry.unresolved == ()

    recipe = normalize_recipe_ingredients(
        make_recipe(
            ingredients=[
                RecipeIngredient(raw_name="Onions", raw_measure="200 g"),
                RecipeIngredient(raw_name="capsicum", raw_measure="1 pc"),  # known alias -> bell_pepper
            ]
        )
    )
    assert recipe.ingredients[0].canonical_id == "onion"
    assert recipe.ingredients[1].canonical_id == "bell_pepper"

    pantry_match = match_pantry(pantry.canonical_ids, recipe.ingredients)
    assert pantry_match.matched_ingredients == ("onion",)
    assert pantry_match.missing_ingredients == ("bell_pepper",)


def test_manual_fallback_price_used_correctly_through_full_chain(price_db):
    # ginger has no LuLu-derived row in this fixture DB; add a manual
    # fallback entry (the same DEC-013 mechanism used in production) and
    # verify the full chain picks it up correctly.
    with connection_scope(price_db, read_only=False) as connection:
        connection.execute(
            """
            INSERT INTO manual_price_entries (
                canonical_id, normalized_unit, display_name, normalized_price_per_unit,
                package_quantity, package_unit, package_price_aed, normalized_package_quantity,
                source_type, provenance_note, collected_at
            ) VALUES ('ginger', 'g', 'Ginger', 0.01296, 250, 'g', 3.24, 250,
                      'manual_curated', 'Founder-approved manual price', '2026-09-06')
            """
        )
        connection.commit()

    repo = PriceRepository(price_db)
    recipe = normalize_recipe_ingredients(
        make_recipe(
            ingredients=[RecipeIngredient(raw_name="ginger", raw_measure="10 g")]
        )
    )
    pantry = normalize_pantry([], canonical_vocabulary=CANONICAL_GROCERY_INGREDIENTS, aliases=GROCERY_INGREDIENT_ALIASES)
    pantry_match = match_pantry(pantry.canonical_ids, recipe.ingredients)
    missing_ingredients = [ing for ing in recipe.ingredients if ing.canonical_id in pantry_match.missing_ingredients]

    cost = estimate_purchase_cost(missing_ingredients, repo)
    assert cost.price_complete is True
    assert cost.estimated_purchase_cost_aed == pytest.approx(3.24)  # one 250 g package covers the 10 g requirement

    candidate = evaluate_candidate(recipe, pantry.canonical_ids, UserConstraints(budget_aed=5.0), cost)
    assert candidate.hard_constraint_pass is True


def test_provenance_survives_from_recipe_through_candidate_evaluation(price_db):
    repo = PriceRepository(price_db)
    recipe = normalize_recipe_ingredients(
        make_recipe(
            id="local_curated:test-nihari-1",
            provider="local_curated",
            provider_recipe_id="test-nihari-1",
            source_label="Test fixture (not production content)",
            provenance_note="Manually authored for audit tests only.",
        )
    )
    pantry = normalize_pantry(
        ["tomato", "onion", "garlic"], canonical_vocabulary=CANONICAL_GROCERY_INGREDIENTS, aliases=GROCERY_INGREDIENT_ALIASES
    )
    cost = estimate_purchase_cost([], repo)
    candidate = evaluate_candidate(recipe, pantry.canonical_ids, UserConstraints(), cost)

    # Provenance identity must survive unchanged from the Recipe DTO
    # into the CandidateEvaluation output.
    assert candidate.recipe_id == recipe.id == "local_curated:test-nihari-1"
    assert candidate.provider == recipe.provider == "local_curated"
    assert recipe.source_label == "Test fixture (not production content)"
    assert recipe.provenance_note == "Manually authored for audit tests only."
