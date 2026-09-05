"""End-to-end deterministic per-recipe evaluation, composing the
pantry matcher (M09) and constraint evaluator (M12) into the
CandidateEvaluation shape the ranker (M13) consumes.

This module does not itself compute real grocery cost (M11/M10 are out
of scope for this ticket); callers supply a CostEvaluation explicitly.
"""

from __future__ import annotations

from app.domain.constraint_evaluator import evaluate_constraints
from app.domain.models import CandidateEvaluation, CostEvaluation, Recipe, UserConstraints
from app.domain.pantry_matcher import match_pantry
from app.domain.ranker import compute_cuisine_score


def evaluate_candidate(
    recipe: Recipe,
    pantry_canonical: frozenset[str],
    constraints: UserConstraints,
    cost: CostEvaluation = CostEvaluation.UNKNOWN,  # type: ignore[attr-defined]
) -> CandidateEvaluation:
    pantry_match = match_pantry(pantry_canonical, recipe.ingredients)
    constraint_result = evaluate_constraints(recipe, constraints, cost)
    cuisine_match = compute_cuisine_score(recipe.cuisine, constraints.cuisine_preference) >= 1.0

    return CandidateEvaluation(
        recipe_id=recipe.id,
        provider=recipe.provider,
        pantry_coverage=pantry_match.pantry_coverage,
        matched_ingredients=list(pantry_match.matched_ingredients),
        missing_ingredients=list(pantry_match.missing_ingredients),
        missing_count=pantry_match.missing_count,
        unresolved_ingredients=list(pantry_match.unresolved_ingredients),
        other_requirements=list(pantry_match.other_requirements),
        estimated_purchase_cost_aed=cost.estimated_purchase_cost_aed,
        price_complete=cost.price_complete,
        cost_confidence=cost.cost_confidence,
        cuisine_match=cuisine_match,
        hard_constraint_pass=constraint_result.hard_constraint_pass,
        rejection_reasons=list(constraint_result.rejection_reasons),
        time_incomplete=constraint_result.time_incomplete,
        deterministic_score=None,
    )
