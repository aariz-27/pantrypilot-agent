from app.domain.constraint_evaluator import evaluate_constraints
from app.domain.models import (
    CostConfidence,
    CostEvaluation,
    Recipe,
    RecipeIngredient,
    RejectionReason,
    UserConstraints,
)


def make_recipe(**overrides):
    defaults = dict(
        id="recipeapi_io:1",
        provider="recipeapi_io",
        provider_recipe_id="1",
        name="Test Recipe",
        cuisine="Chinese",
        ingredients=[RecipeIngredient(raw_name="rice", canonical_id="rice")],
        instructions="Cook the rice.",
        prep_time_minutes=10,
        cook_time_minutes=20,
    )
    defaults.update(overrides)
    return Recipe(**defaults)


def test_passing_recipe_has_no_rejection_reasons():
    result = evaluate_constraints(make_recipe(), UserConstraints())
    assert result.hard_constraint_pass is True
    assert result.rejection_reasons == ()


def test_excluded_ingredient_present():
    recipe = make_recipe(
        ingredients=[
            RecipeIngredient(raw_name="rice", canonical_id="rice"),
            RecipeIngredient(raw_name="garlic", canonical_id="garlic"),
        ]
    )
    constraints = UserConstraints(excluded_canonical=frozenset({"garlic"}))
    result = evaluate_constraints(recipe, constraints)
    assert result.hard_constraint_pass is False
    assert RejectionReason.EXCLUDED_INGREDIENT_PRESENT in result.rejection_reasons


def test_excluded_ingredient_present_even_when_marked_optional():
    # Test-coverage gap (audit finding, 2026-09-07): an exclusion is a
    # hard user-safety rule (e.g. an allergy) and must apply even to an
    # ingredient marked optional (e.g. an "optional garnish" of peanuts)
    # -- the code already enforces this (constraint_evaluator.py checks
    # every ingredient regardless of `optional`), but no test previously
    # proved it.
    recipe = make_recipe(
        ingredients=[
            RecipeIngredient(raw_name="rice", canonical_id="rice"),
            RecipeIngredient(raw_name="peanuts", canonical_id="peanut", optional=True),
        ]
    )
    constraints = UserConstraints(excluded_canonical=frozenset({"peanut"}))
    result = evaluate_constraints(recipe, constraints)
    assert result.hard_constraint_pass is False
    assert RejectionReason.EXCLUDED_INGREDIENT_PRESENT in result.rejection_reasons


def test_excluded_ingredient_absent_passes():
    recipe = make_recipe()
    constraints = UserConstraints(excluded_canonical=frozenset({"garlic"}))
    result = evaluate_constraints(recipe, constraints)
    assert result.hard_constraint_pass is True


def test_strict_cuisine_mismatch_rejected():
    recipe = make_recipe(cuisine="Italian")
    constraints = UserConstraints(cuisine_preference="Indian", cuisine_strict=True)
    result = evaluate_constraints(recipe, constraints)
    assert RejectionReason.STRICT_CUISINE_MISMATCH in result.rejection_reasons


def test_strict_cuisine_match_passes():
    recipe = make_recipe(cuisine="Indian")
    constraints = UserConstraints(cuisine_preference="indian", cuisine_strict=True)
    result = evaluate_constraints(recipe, constraints)
    assert result.hard_constraint_pass is True


def test_strict_cuisine_unknown_recipe_cuisine_rejected():
    recipe = make_recipe(cuisine=None)
    constraints = UserConstraints(cuisine_preference="Indian", cuisine_strict=True)
    result = evaluate_constraints(recipe, constraints)
    assert RejectionReason.STRICT_CUISINE_MISMATCH in result.rejection_reasons


def test_soft_cuisine_mismatch_does_not_reject():
    recipe = make_recipe(cuisine="Italian")
    constraints = UserConstraints(cuisine_preference="Indian", cuisine_strict=False)
    result = evaluate_constraints(recipe, constraints)
    assert result.hard_constraint_pass is True


def test_budget_exceeded_with_complete_cost_rejects():
    cost = CostEvaluation(estimated_purchase_cost_aed=15.0, price_complete=True, cost_confidence=CostConfidence.HIGH)
    constraints = UserConstraints(budget_aed=10.0)
    result = evaluate_constraints(make_recipe(), constraints, cost)
    assert RejectionReason.BUDGET_EXCEEDED in result.rejection_reasons


def test_budget_within_range_passes():
    cost = CostEvaluation(estimated_purchase_cost_aed=5.0, price_complete=True, cost_confidence=CostConfidence.HIGH)
    constraints = UserConstraints(budget_aed=10.0)
    result = evaluate_constraints(make_recipe(), constraints, cost)
    assert result.hard_constraint_pass is True


def test_zero_budget_zero_cost_passes():
    cost = CostEvaluation(estimated_purchase_cost_aed=0.0, price_complete=True, cost_confidence=CostConfidence.HIGH)
    constraints = UserConstraints(budget_aed=0.0)
    result = evaluate_constraints(make_recipe(), constraints, cost)
    assert result.hard_constraint_pass is True


def test_zero_budget_positive_cost_hard_fails():
    cost = CostEvaluation(estimated_purchase_cost_aed=0.5, price_complete=True, cost_confidence=CostConfidence.HIGH)
    constraints = UserConstraints(budget_aed=0.0)
    result = evaluate_constraints(make_recipe(), constraints, cost)
    assert RejectionReason.BUDGET_EXCEEDED in result.rejection_reasons


def test_positive_budget_plus_incomplete_cost_is_indeterminate_not_feasible():
    # Regression for defect: a supplied positive budget with incomplete
    # cost must not be classified as fully feasible. It must also never
    # be treated as if the cost were zero or fabricated.
    cost = CostEvaluation()  # price_complete=False, cost=None -- CostEvaluation.UNKNOWN
    constraints = UserConstraints(budget_aed=10.0)
    result = evaluate_constraints(make_recipe(), constraints, cost)
    assert result.hard_constraint_pass is False
    assert RejectionReason.BUDGET_INDETERMINATE_COST_INCOMPLETE in result.rejection_reasons
    assert RejectionReason.BUDGET_EXCEEDED not in result.rejection_reasons
    assert result.cost_incomplete is True
    assert cost.estimated_purchase_cost_aed is None


def test_zero_budget_plus_incomplete_cost_is_indeterminate_not_feasible():
    # A zero budget is still "a budget supplied" -- incomplete cost must
    # not be silently accepted as within a zero budget.
    cost = CostEvaluation()
    constraints = UserConstraints(budget_aed=0.0)
    result = evaluate_constraints(make_recipe(), constraints, cost)
    assert result.hard_constraint_pass is False
    assert RejectionReason.BUDGET_INDETERMINATE_COST_INCOMPLETE in result.rejection_reasons
    assert result.cost_incomplete is True


def test_complete_known_cost_within_budget_is_feasible():
    cost = CostEvaluation(estimated_purchase_cost_aed=5.0, price_complete=True, cost_confidence=CostConfidence.HIGH)
    constraints = UserConstraints(budget_aed=10.0)
    result = evaluate_constraints(make_recipe(), constraints, cost)
    assert result.hard_constraint_pass is True
    assert result.rejection_reasons == ()
    assert result.cost_incomplete is False


def test_complete_known_cost_exceeding_budget_is_rejected():
    cost = CostEvaluation(estimated_purchase_cost_aed=15.0, price_complete=True, cost_confidence=CostConfidence.HIGH)
    constraints = UserConstraints(budget_aed=10.0)
    result = evaluate_constraints(make_recipe(), constraints, cost)
    assert result.hard_constraint_pass is False
    assert RejectionReason.BUDGET_EXCEEDED in result.rejection_reasons
    assert RejectionReason.BUDGET_INDETERMINATE_COST_INCOMPLETE not in result.rejection_reasons


def test_incomplete_cost_without_any_budget_remains_feasible():
    # No budget was supplied at all, so cost incompleteness is not a
    # budget-feasibility concern -- this must remain unaffected by the fix.
    cost = CostEvaluation()
    constraints = UserConstraints(budget_aed=None)
    result = evaluate_constraints(make_recipe(), constraints, cost)
    assert result.hard_constraint_pass is True
    assert result.cost_incomplete is True


def test_max_total_time_exceeded_rejects():
    recipe = make_recipe(prep_time_minutes=30, cook_time_minutes=30)
    constraints = UserConstraints(max_total_time_minutes=45)
    result = evaluate_constraints(recipe, constraints)
    assert RejectionReason.MAX_TOTAL_TIME_EXCEEDED in result.rejection_reasons


def test_max_total_time_within_range_passes():
    recipe = make_recipe(prep_time_minutes=10, cook_time_minutes=20)
    constraints = UserConstraints(max_total_time_minutes=45)
    result = evaluate_constraints(recipe, constraints)
    assert result.hard_constraint_pass is True


def test_max_total_time_uses_prep_plus_cook_not_prep_alone():
    # 20 + 20 = 40 > 30, must be rejected even though prep alone (20) is within range.
    recipe = make_recipe(prep_time_minutes=20, cook_time_minutes=20)
    constraints = UserConstraints(max_total_time_minutes=30)
    result = evaluate_constraints(recipe, constraints)
    assert RejectionReason.MAX_TOTAL_TIME_EXCEEDED in result.rejection_reasons


def test_max_total_time_missing_components_is_hard_fail_not_silently_ignored():
    recipe = make_recipe(prep_time_minutes=None, cook_time_minutes=None)
    constraints = UserConstraints(max_total_time_minutes=45)
    result = evaluate_constraints(recipe, constraints)
    assert result.hard_constraint_pass is False
    assert RejectionReason.TIME_INCOMPLETE_WITH_CONSTRAINT in result.rejection_reasons
    assert result.time_incomplete is True


def test_no_time_constraint_ignores_missing_time_components():
    recipe = make_recipe(prep_time_minutes=None, cook_time_minutes=None)
    result = evaluate_constraints(recipe, UserConstraints())
    assert result.hard_constraint_pass is True


def test_recipe_lacking_instructions_rejected():
    recipe = make_recipe(instructions="   ")
    result = evaluate_constraints(recipe, UserConstraints())
    assert RejectionReason.INSTRUCTIONS_UNUSABLE in result.rejection_reasons


def test_recipe_lacking_ingredient_list_rejected():
    recipe = make_recipe(ingredients=[])
    result = evaluate_constraints(recipe, UserConstraints())
    assert RejectionReason.INGREDIENT_LIST_UNUSABLE in result.rejection_reasons


def test_invalid_provenance_missing_provider_recipe_id_rejected():
    recipe = make_recipe(provider_recipe_id="  ")
    result = evaluate_constraints(recipe, UserConstraints())
    assert RejectionReason.PROVENANCE_INVALID in result.rejection_reasons


def test_combined_failures_report_all_reasons():
    recipe = make_recipe(
        cuisine="Italian",
        instructions="",
        ingredients=[RecipeIngredient(raw_name="garlic", canonical_id="garlic")],
    )
    constraints = UserConstraints(
        cuisine_preference="Indian",
        cuisine_strict=True,
        excluded_canonical=frozenset({"garlic"}),
    )
    result = evaluate_constraints(recipe, constraints)
    assert RejectionReason.STRICT_CUISINE_MISMATCH in result.rejection_reasons
    assert RejectionReason.INSTRUCTIONS_UNUSABLE in result.rejection_reasons
    assert RejectionReason.EXCLUDED_INGREDIENT_PRESENT in result.rejection_reasons
    assert result.hard_constraint_pass is False
