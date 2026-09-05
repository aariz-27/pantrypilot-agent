import pytest

from app.domain.candidate_evaluation import evaluate_candidate
from app.domain.models import CostConfidence, CostEvaluation, Recipe, RecipeIngredient, RejectionReason, UserConstraints


def make_recipe(**overrides):
    defaults = dict(
        id="recipeapi_io:1",
        provider="recipeapi_io",
        provider_recipe_id="1",
        name="Chicken Rice",
        cuisine="Chinese",
        ingredients=[
            RecipeIngredient(raw_name="chicken breast", canonical_id="chicken_breast"),
            RecipeIngredient(raw_name="rice", canonical_id="rice"),
            RecipeIngredient(raw_name="soy sauce", canonical_id="soy_sauce"),
        ],
        instructions="Cook everything.",
    )
    defaults.update(overrides)
    return Recipe(**defaults)


def test_feasible_candidate_end_to_end():
    pantry = frozenset({"chicken_breast", "rice"})
    cost = CostEvaluation(estimated_purchase_cost_aed=5.5, price_complete=True, cost_confidence=CostConfidence.HIGH)
    constraints = UserConstraints(budget_aed=10.0, cuisine_preference="Chinese")

    result = evaluate_candidate(make_recipe(), pantry, constraints, cost)

    assert result.hard_constraint_pass is True
    assert result.pantry_coverage == pytest.approx(2 / 3)
    assert result.missing_ingredients == ["soy_sauce"]
    assert result.cuisine_match is True
    assert result.price_complete is True
    assert result.deterministic_score is None  # ranking is a separate step


def test_infeasible_candidate_reports_rejection_reasons_not_an_exception():
    pantry = frozenset({"chicken_breast", "rice"})
    constraints = UserConstraints(excluded_canonical=frozenset({"soy_sauce"}))

    result = evaluate_candidate(make_recipe(), pantry, constraints)

    assert result.hard_constraint_pass is False
    assert RejectionReason.EXCLUDED_INGREDIENT_PRESENT in result.rejection_reasons


def test_unknown_cost_defaults_are_never_treated_as_zero():
    pantry = frozenset({"chicken_breast", "rice", "soy_sauce"})
    result = evaluate_candidate(make_recipe(), pantry, UserConstraints())
    assert result.price_complete is False
    assert result.estimated_purchase_cost_aed is None
