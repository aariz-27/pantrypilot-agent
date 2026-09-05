"""Deterministic ranking/scoring foundation (M13).

Implements the approved formula and weights from TECHNICAL_SPEC.md
section 14 exactly:

    score = 0.45*coverage + 0.30*cost_score + 0.15*missing_score + 0.10*cuisine_score

This module only ranks candidates that have already passed hard
constraints (M12). It does not compute real grocery cost -- it accepts
CostEvaluation as an explicit input so the real Cost Engine (M11) can
plug in later without redesigning this module (ticket cost rule).

rank_candidates() also performs a second-line defensive re-check of the
one invariant it can itself observe from its own inputs (a supplied
budget vs. a candidate's cost fields, see _assert_budget_feasible). This
closes an alternate-call-sequence escape path where a caller passes a
CandidateEvaluation with hard_constraint_pass incorrectly set to True,
bypassing evaluate_constraints() entirely. evaluate_constraints()
remains the single authoritative constraint evaluator; this re-check
does not duplicate the exclusion/cuisine/time logic that only
evaluate_constraints() has the original Recipe to verify.

Documented implementation assumption (spec does not give an exact
number for this case; it resolves conservatively, consistent with the
spec's stated philosophy of never rewarding unknown cost):

No cuisine preference at all (cuisine_preference is None): the spec
only defines exact-match/unknown/non-match scores relative to a stated
preference. Absence of any preference scores 1.0 (neutral), so the 10%
cuisine weight does not penalize a user who expressed no preference.
This is narrow, numeric, and does not affect hard constraints,
provenance, or architecture. It is flagged here and in the PR readiness
report for Founder/ChatGPT review rather than blocking this ticket.

Note on the conservative 0.25 incomplete-cost score: it is only ever
reachable for the no-budget case (_cost_scores_without_budget), where
cost cannot be judged against anything and 0.25 remains the documented
conservative default. With a budget supplied, incomplete cost is now a
rejected invariant violation (see _assert_budget_feasible) rather than
a scored outcome, so the with-budget branch inside
_cost_score_with_budget that returns 0.25 is unreachable through
rank_candidates and exists only as a defensive fallback for direct
callers of that private helper.
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


def _assert_budget_feasible(candidate: CandidateEvaluation, budget_aed: float | None) -> None:
    """Second-line defensive check.

    evaluate_constraints() is the authoritative source of truth for
    budget feasibility (TECHNICAL_SPEC.md section 14). This is a
    redundant, ranker-local re-check of only the budget invariant the
    ranker can itself observe from CandidateEvaluation + UserConstraints
    -- it must not duplicate exclusion/cuisine/time logic, which the
    ranker has no way to re-derive without the original Recipe. Its
    purpose is to close the alternate-call-sequence escape path where a
    caller constructs/passes a CandidateEvaluation with
    hard_constraint_pass incorrectly set to True, bypassing
    evaluate_constraints() entirely.
    """

    if budget_aed is None:
        return

    if not candidate.price_complete or candidate.estimated_purchase_cost_aed is None:
        raise InvalidInputError(
            "rank_candidates received a candidate marked hard_constraint_pass=True with "
            f"incomplete cost under a supplied budget (recipe_id={candidate.recipe_id}). "
            "Incomplete cost with a supplied budget can never be feasible "
            "(TECHNICAL_SPEC.md section 14); evaluate_constraints() should have rejected it."
        )

    if candidate.estimated_purchase_cost_aed > budget_aed:
        raise InvalidInputError(
            "rank_candidates received a candidate marked hard_constraint_pass=True with a "
            f"known cost ({candidate.estimated_purchase_cost_aed}) exceeding the supplied "
            f"budget ({budget_aed}) for recipe_id={candidate.recipe_id}; "
            "evaluate_constraints() should have rejected it."
        )


def rank_candidates(
    candidates: list[CandidateEvaluation],
    constraints: UserConstraints,
    recipe_cuisine_by_id: dict[str, str | None],
    recipe_name_by_id: dict[str, str],
) -> list[CandidateEvaluation]:
    """Score and deterministically order a list of already-feasible
    candidate evaluations. Raises InvalidInputError if any candidate has
    not passed hard constraints, or if a candidate's own budget-related
    fields directly contradict the supplied budget despite claiming to
    be feasible -- ranking such a candidate is not part of this module's
    contract, and evaluate_constraints() remains the authoritative
    constraint evaluator."""

    for candidate in candidates:
        if not candidate.hard_constraint_pass:
            raise InvalidInputError(
                f"rank_candidates received a non-feasible candidate: {candidate.recipe_id}"
            )
        _assert_budget_feasible(candidate, constraints.budget_aed)

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
