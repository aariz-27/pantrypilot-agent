"""Regression tests for app.api.recommend_mapping's budget-deviation
label (PR #15 bug fix, 2026-09-09).

Live browser reproduction traced this ticket's confirmed "recipe shows
an additional cost under budget but is still labeled over budget" bug
to a FRONTEND-ONLY defect (frontend/src/domain/pantryRecompute.js's
applyExtraPantryToCard carried a card's deviation_reasons forward
unchanged after locally recomputing its cost -- see
frontend/src/domain/pantryRecompute.test.js for the fix and its
regression coverage).

This file exists to positively confirm, at the layer the ticket
describes (independent per-request budget comparison), that the
BACKEND was never the source of staleness: the exact same
CandidateEvaluation object, reused across two calls with different
budget_aed values, produces independently correct deviation text each
time -- no shared/cached state, no cross-call contamination.
"""

from __future__ import annotations

from app.api.recommend_mapping import _deviation_reasons
from app.domain.models import CandidateEvaluation, CostConfidence, RejectionReason


def _over_budget_candidate(cost_aed: float, *, price_complete: bool = True) -> CandidateEvaluation:
    return CandidateEvaluation(
        recipe_id="recipeapi_io:1",
        provider="recipeapi_io",
        pantry_coverage=0.5,
        matched_ingredients=["chicken_breast"],
        missing_ingredients=["mozzarella_cheese"],
        missing_count=1,
        estimated_purchase_cost_aed=cost_aed if price_complete else None,
        price_complete=price_complete,
        cost_confidence=CostConfidence.HIGH if price_complete else CostConfidence.UNKNOWN,
        cuisine_match=True,
        hard_constraint_pass=False,
        rejection_reasons=[RejectionReason.BUDGET_EXCEEDED] if price_complete else [RejectionReason.BUDGET_INDETERMINATE_COST_INCOMPLETE],
        deterministic_score=None,
    )


# --- Case A: budget increases between searches -------------------------------


def test_case_a_budget_increase_is_not_stale_across_two_calls():
    """Search 1 (budget 10) then search 2 (budget 50), SAME candidate
    object (cost 21.60) reused -- search 2 must show no "over budget"
    reason at all, never search 1's stale comparison."""

    candidate = _over_budget_candidate(21.60)

    search_1 = _deviation_reasons(candidate, recipe=None, max_total_time_minutes=None, budget_aed=10)
    assert search_1 == ["Est. AED 11.60 over budget"]

    search_2 = _deviation_reasons(candidate, recipe=None, max_total_time_minutes=None, budget_aed=50)
    assert search_2 == []


# --- Case B: budget decreases between searches -------------------------------


def test_case_b_budget_decrease_is_honored():
    candidate = _over_budget_candidate(21.60)

    search_1 = _deviation_reasons(candidate, recipe=None, max_total_time_minutes=None, budget_aed=50)
    assert search_1 == []

    search_2 = _deviation_reasons(candidate, recipe=None, max_total_time_minutes=None, budget_aed=10)
    assert search_2 == ["Est. AED 11.60 over budget"]


# --- Case C: no budget --------------------------------------------------------


def test_case_c_no_budget_never_shows_a_comparison():
    candidate = _over_budget_candidate(21.60)
    result = _deviation_reasons(candidate, recipe=None, max_total_time_minutes=None, budget_aed=None)
    assert result == []


# --- Case D: incomplete price --------------------------------------------------


def test_case_d_incomplete_price_never_inferred_as_within_budget():
    candidate = _over_budget_candidate(cost_aed=0, price_complete=False)
    result = _deviation_reasons(candidate, recipe=None, max_total_time_minutes=None, budget_aed=50)
    # Never a fabricated "over budget" claim from an unknown cost, and
    # never silently treated as safely affordable either -- no reason at
    # all is the correct, conservative outcome (the card's own
    # price_complete=False already signals the uncertainty separately).
    assert result == []


def test_exactly_at_budget_is_not_over_budget():
    candidate = _over_budget_candidate(50.0)
    result = _deviation_reasons(candidate, recipe=None, max_total_time_minutes=None, budget_aed=50)
    assert result == []


def test_over_budget_amount_is_computed_fresh_not_cached_between_unrelated_candidates():
    # Two DIFFERENT candidate objects, same budget -- proves the
    # computation is a pure function of its own arguments, not a
    # shared/memoized value keyed by something narrower than the full
    # (cost, budget) pair.
    cheap = _over_budget_candidate(5.0)
    expensive = _over_budget_candidate(120.0)

    assert _deviation_reasons(cheap, recipe=None, max_total_time_minutes=None, budget_aed=10) == []
    assert _deviation_reasons(expensive, recipe=None, max_total_time_minutes=None, budget_aed=10) == ["Est. AED 110.00 over budget"]
    # Re-checking the first candidate again afterwards must be unaffected
    # by having just evaluated a completely different, much larger cost.
    assert _deviation_reasons(cheap, recipe=None, max_total_time_minutes=None, budget_aed=10) == []
