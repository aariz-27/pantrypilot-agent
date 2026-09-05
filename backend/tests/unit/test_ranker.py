import pytest

from app.domain.errors import InvalidInputError
from app.domain.models import CandidateEvaluation, CostConfidence, UserConstraints
from app.domain.ranker import (
    compute_cuisine_score,
    compute_missing_score,
    rank_candidates,
)


def make_candidate(**overrides):
    defaults = dict(
        recipe_id="r1",
        provider="recipeapi_io",
        pantry_coverage=0.8,
        matched_ingredients=["a"],
        missing_ingredients=["b"],
        missing_count=1,
        estimated_purchase_cost_aed=5.0,
        price_complete=True,
        cost_confidence=CostConfidence.HIGH,
        cuisine_match=True,
        hard_constraint_pass=True,
        rejection_reasons=[],
    )
    defaults.update(overrides)
    return CandidateEvaluation(**defaults)


def test_missing_score_formula():
    assert compute_missing_score(0) == 1.0
    assert compute_missing_score(5) == 0.0
    assert compute_missing_score(10) == 0.0  # clamped
    assert compute_missing_score(1) == pytest.approx(0.8)


def test_cuisine_score_exact_match():
    assert compute_cuisine_score("Chinese", "chinese") == 1.0


def test_cuisine_score_unknown_recipe_cuisine_under_soft_preference():
    assert compute_cuisine_score(None, "Chinese") == 0.5


def test_cuisine_score_known_non_match():
    assert compute_cuisine_score("Italian", "Chinese") == 0.0


def test_cuisine_score_no_preference_is_neutral():
    assert compute_cuisine_score("Italian", None) == 1.0


def test_score_formula_with_budget_matches_spec_weights():
    candidate = make_candidate(
        pantry_coverage=0.8,
        missing_count=1,
        estimated_purchase_cost_aed=5.0,
        price_complete=True,
    )
    constraints = UserConstraints(budget_aed=10.0, cuisine_preference="Chinese")
    [ranked] = rank_candidates(
        [candidate],
        constraints,
        recipe_cuisine_by_id={"r1": "Chinese"},
        recipe_name_by_id={"r1": "Test"},
    )
    # coverage=0.8 cost_score=1-5/10=0.5 missing_score=1-1/5=0.8 cuisine_score=1.0
    expected = 0.45 * 0.8 + 0.30 * 0.5 + 0.15 * 0.8 + 0.10 * 1.0
    assert ranked.deterministic_score == pytest.approx(expected)


def test_zero_budget_zero_known_cost_scores_full_cost_component():
    candidate = make_candidate(estimated_purchase_cost_aed=0.0, price_complete=True)
    constraints = UserConstraints(budget_aed=0.0)
    [ranked] = rank_candidates(
        [candidate], constraints, recipe_cuisine_by_id={}, recipe_name_by_id={"r1": "Test"}
    )
    expected = 0.45 * 0.8 + 0.30 * 1.0 + 0.15 * 0.8 + 0.10 * 1.0
    assert ranked.deterministic_score == pytest.approx(expected)


def test_incomplete_cost_never_scores_as_if_free():
    candidate = make_candidate(estimated_purchase_cost_aed=None, price_complete=False, cost_confidence=CostConfidence.UNKNOWN)
    constraints = UserConstraints(budget_aed=10.0)
    [ranked] = rank_candidates(
        [candidate], constraints, recipe_cuisine_by_id={}, recipe_name_by_id={"r1": "Test"}
    )
    expected = 0.45 * 0.8 + 0.30 * 0.25 + 0.15 * 0.8 + 0.10 * 1.0
    assert ranked.deterministic_score == pytest.approx(expected)


def test_without_budget_cost_normalized_within_candidate_set():
    cheap = make_candidate(recipe_id="cheap", estimated_purchase_cost_aed=2.0, price_complete=True)
    expensive = make_candidate(recipe_id="expensive", estimated_purchase_cost_aed=10.0, price_complete=True)
    constraints = UserConstraints(budget_aed=None)
    ranked = rank_candidates(
        [cheap, expensive],
        constraints,
        recipe_cuisine_by_id={},
        recipe_name_by_id={"cheap": "Cheap", "expensive": "Expensive"},
    )
    by_id = {c.recipe_id: c for c in ranked}
    assert by_id["cheap"].deterministic_score > by_id["expensive"].deterministic_score


def test_without_budget_all_incomplete_cost_uses_conservative_score():
    candidate = make_candidate(estimated_purchase_cost_aed=None, price_complete=False, cost_confidence=CostConfidence.UNKNOWN)
    constraints = UserConstraints(budget_aed=None)
    [ranked] = rank_candidates(
        [candidate], constraints, recipe_cuisine_by_id={}, recipe_name_by_id={"r1": "Test"}
    )
    expected = 0.45 * 0.8 + 0.30 * 0.25 + 0.15 * 0.8 + 0.10 * 1.0
    assert ranked.deterministic_score == pytest.approx(expected)


def test_tie_break_prefers_complete_price_over_incomplete_at_equal_score():
    # Force equal deterministic_score by giving both candidates identical
    # coverage/missing/cuisine and equal cost_score outcome (both budget-free
    # normalization collapses to 1.0 when only one has a complete price).
    complete = make_candidate(
        recipe_id="complete", pantry_coverage=0.5, missing_count=2, estimated_purchase_cost_aed=5.0, price_complete=True
    )
    incomplete = make_candidate(
        recipe_id="incomplete", pantry_coverage=0.5, missing_count=2, estimated_purchase_cost_aed=None, price_complete=False, cost_confidence=CostConfidence.UNKNOWN
    )
    constraints = UserConstraints(budget_aed=None)
    ranked = rank_candidates(
        [incomplete, complete],
        constraints,
        recipe_cuisine_by_id={},
        recipe_name_by_id={"complete": "A", "incomplete": "B"},
    )
    # complete has cost_score=1.0 (only complete cost in the set) so it should
    # score strictly higher and be ranked first regardless of tie-break.
    assert ranked[0].recipe_id == "complete"


def test_tie_break_alphabetical_when_everything_else_equal():
    a = make_candidate(recipe_id="a", pantry_coverage=0.6, missing_count=1, estimated_purchase_cost_aed=5.0, price_complete=True)
    b = make_candidate(recipe_id="b", pantry_coverage=0.6, missing_count=1, estimated_purchase_cost_aed=5.0, price_complete=True)
    constraints = UserConstraints(budget_aed=10.0)
    ranked = rank_candidates(
        [b, a],
        constraints,
        recipe_cuisine_by_id={},
        recipe_name_by_id={"a": "Alpha Dish", "b": "Beta Dish"},
    )
    assert [c.recipe_id for c in ranked] == ["a", "b"]


def test_identical_inputs_produce_identical_order_ac14():
    candidates = [
        make_candidate(recipe_id="x", pantry_coverage=0.9, missing_count=0, estimated_purchase_cost_aed=1.0, price_complete=True),
        make_candidate(recipe_id="y", pantry_coverage=0.5, missing_count=3, estimated_purchase_cost_aed=8.0, price_complete=True),
    ]
    constraints = UserConstraints(budget_aed=10.0, cuisine_preference="Chinese")
    names = {"x": "X", "y": "Y"}
    cuisines = {"x": "Chinese", "y": "Chinese"}

    order_1 = [c.recipe_id for c in rank_candidates(candidates, constraints, cuisines, names)]
    order_2 = [c.recipe_id for c in rank_candidates(candidates, constraints, cuisines, names)]
    assert order_1 == order_2


def test_rank_candidates_rejects_non_feasible_input():
    candidate = make_candidate(hard_constraint_pass=False)
    with pytest.raises(InvalidInputError):
        rank_candidates([candidate], UserConstraints(), {}, {})
