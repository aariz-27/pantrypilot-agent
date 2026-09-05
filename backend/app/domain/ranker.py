"""Deterministic ranking/scoring foundation (M13).

Implements the approved formula and weights from TECHNICAL_SPEC.md
section 14 exactly:

    score = 0.45*coverage + 0.30*cost_score + 0.15*missing_score + 0.10*cuisine_score

This module only ranks candidates that have already passed hard
constraints (M12). It does not compute real grocery cost -- it accepts
CostEvaluation as an explicit input so the real Cost Engine (M11) can
plug in later without redesigning this module (ticket cost rule).

Documented implementation assumptions (spec does not give an exact
number for these two cases; both resolve conservatively, consistent
with the spec's stated philosophy of never rewarding unknown cost or
penalizing an unspecified preference):

1. Incomplete cost WITH a budget specified: the spec explicitly defines
   the conservative 0.25 cost_score only for the "without budget" case.
   This implementation applies the same conservative 0.25 whenever cost
   is incomplete, regardless of whether a budget was specified, because
   leaving the with-budget+incomplete case fully unscored would be
   worse than extending the documented conservative convention.
2. No cuisine preference at all (cuisine_preference is None): the spec
   only defines exact-match/unknown/non-match scores relative to a
   stated preference. Absence of any preference scores 1.0 (neutral),
   so the 10% cuisine weight does not penalize a user who expressed no
   preference.

Both assumptions are narrow, numeric, and do not affect hard
constraints, provenance, or architecture. They are flagged here and in
the PR readiness report for Founder/ChatGPT review rather than blocking
this ticket.
"""

from __future__ import annotations

from app.domain.errors import InvalidInputError
from app.domain.models import CandidateEvaluation, CostConfidence, UserConstraints

COVERAGE_WEIGHT = 0.45
COST_WEIGHT = 0.30
MISSING_WEIGHT = 0.15
CUISINE_WEIGHT = 0.10

_INCOMPLETE_COST_SCORE = 0.25

_CONFIDENCE_RANK = {
    CostConfidence.HIGH: 0,
    CostConfidence.MEDIUM: 1,
    CostConfidence.LOW: 2,
    CostConfidence.UNKNOWN: 3,
}


def compute_missing_score(missing_count: int) -> float:
    return 1 - min(missing_count / 5, 1)


def compute_cuisine_score(recipe_cuisine: str | None, preference: str | None) -> float:
    if preference is None:
        return 1.0
    recipe_c = (recipe_cuisine or "").strip().lower()
    if not recipe_c:
        return 0.5
    return 1.0 if recipe_c == preference.strip().lower() else 0.0


def _cost_score_with_budget(candidate: CandidateEvaluation, budget_aed: float) -> float:
    if not candidate.price_complete or candidate.estimated_purchase_cost_aed is None:
        return _INCOMPLETE_COST_SCORE
    if budget_aed == 0:
        return 1.0 if candidate.estimated_purchase_cost_aed == 0 else 0.0
    return max(0.0, 1 - candidate.estimated_purchase_cost_aed / max(budget_aed, 1))


def _cost_scores_without_budget(candidates: list[CandidateEvaluation]) -> list[float]:
    complete_costs = [
        c.estimated_purchase_cost_aed
        for c in candidates
        if c.price_complete and c.estimated_purchase_cost_aed is not None
    ]
    if not complete_costs:
        return [_INCOMPLETE_COST_SCORE for _ in candidates]

    min_cost, max_cost = min(complete_costs), max(complete_costs)
    scores: list[float] = []
    for candidate in candidates:
        if not candidate.price_complete or candidate.estimated_purchase_cost_aed is None:
            scores.append(_INCOMPLETE_COST_SCORE)
        elif max_cost == min_cost:
            scores.append(1.0)
        else:
            scores.append(
                1 - (candidate.estimated_purchase_cost_aed - min_cost) / (max_cost - min_cost)
            )
    return scores


def _tie_break_key(candidate: CandidateEvaluation, recipe_cuisine_by_id: dict[str, str | None], name_by_id: dict[str, str]):
    confidence_rank = _CONFIDENCE_RANK[candidate.cost_confidence]
    price_rank = 0 if candidate.price_complete else 1
    cost_for_sort = (
        candidate.estimated_purchase_cost_aed
        if candidate.price_complete and candidate.estimated_purchase_cost_aed is not None
        else float("inf")
    )
    name = name_by_id.get(candidate.recipe_id, "")
    return (
        -(candidate.deterministic_score or 0.0),
        price_rank,
        confidence_rank,
        -candidate.pantry_coverage,
        cost_for_sort,
        candidate.missing_count,
        name.lower(),
    )


def rank_candidates(
    candidates: list[CandidateEvaluation],
    constraints: UserConstraints,
    recipe_cuisine_by_id: dict[str, str | None],
    recipe_name_by_id: dict[str, str],
) -> list[CandidateEvaluation]:
    """Score and deterministically order a list of already-feasible
    candidate evaluations. Raises InvalidInputError if any candidate has
    not passed hard constraints, since ranking infeasible candidates is
    not part of this module's contract."""

    for candidate in candidates:
        if not candidate.hard_constraint_pass:
            raise InvalidInputError(
                f"rank_candidates received a non-feasible candidate: {candidate.recipe_id}"
            )

    if constraints.budget_aed is None:
        cost_scores = _cost_scores_without_budget(candidates)
    else:
        cost_scores = [_cost_score_with_budget(c, constraints.budget_aed) for c in candidates]

    scored: list[CandidateEvaluation] = []
    for candidate, cost_score in zip(candidates, cost_scores):
        missing_score = compute_missing_score(candidate.missing_count)
        cuisine_score = compute_cuisine_score(
            recipe_cuisine_by_id.get(candidate.recipe_id), constraints.cuisine_preference
        )
        score = (
            COVERAGE_WEIGHT * candidate.pantry_coverage
            + COST_WEIGHT * cost_score
            + MISSING_WEIGHT * missing_score
            + CUISINE_WEIGHT * cuisine_score
        )
        scored.append(candidate.model_copy(update={"deterministic_score": score}))

    return sorted(
        scored,
        key=lambda c: _tie_break_key(c, recipe_cuisine_by_id, recipe_name_by_id),
    )
