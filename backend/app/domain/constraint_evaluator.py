"""Hard-constraint evaluation (M12 subset).

Implements the hard-failure checks from TECHNICAL_SPEC.md section 14
that are in scope for this ticket: exclusions, strict cuisine, optional
max-total-time, and recipe usability/provenance foundations.

Real purchase-cost calculation (M11) and price lookup (M10) are out of
scope; this evaluator accepts a CostEvaluation as an explicit input
(see app.domain.models.CostEvaluation) so the real Cost Engine can plug
in later without changing this evaluator's design.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.models import CostEvaluation, Recipe, RejectionReason, UserConstraints


@dataclass(frozen=True)
class ConstraintEvaluationResult:
    hard_constraint_pass: bool
    rejection_reasons: tuple[RejectionReason, ...] = field(default_factory=tuple)
    time_incomplete: bool = False
    cost_incomplete: bool = False


def _is_blank(value: str | None) -> bool:
    return value is None or not value.strip()


def evaluate_constraints(
    recipe: Recipe,
    constraints: UserConstraints,
    cost: CostEvaluation = CostEvaluation.UNKNOWN,  # type: ignore[attr-defined]
) -> ConstraintEvaluationResult:
    reasons: list[RejectionReason] = []

    # Provenance and usability foundations.
    if _is_blank(recipe.provider) or _is_blank(recipe.provider_recipe_id) or _is_blank(recipe.name):
        reasons.append(RejectionReason.PROVENANCE_INVALID)

    if not recipe.ingredients:
        reasons.append(RejectionReason.INGREDIENT_LIST_UNUSABLE)

    if _is_blank(recipe.instructions):
        reasons.append(RejectionReason.INSTRUCTIONS_UNUSABLE)

    # Exclusion enforcement: applies to every ingredient regardless of
    # optional/matched status, since it is a hard user-safety rule.
    recipe_canonical_ids = {
        ing.canonical_id for ing in recipe.ingredients if ing.canonical_id is not None
    }
    if recipe_canonical_ids & constraints.excluded_canonical:
        reasons.append(RejectionReason.EXCLUDED_INGREDIENT_PRESENT)

    # Strict cuisine enforcement.
    if constraints.cuisine_strict and constraints.cuisine_preference:
        recipe_cuisine = (recipe.cuisine or "").strip().lower()
        preferred = constraints.cuisine_preference.strip().lower()
        if recipe_cuisine != preferred:
            reasons.append(RejectionReason.STRICT_CUISINE_MISMATCH)

    # Optional maximum total time = prep + cook, computed locally.
    # RecipeAPI.io's max_prep_time must never substitute for this.
    time_incomplete = False
    if constraints.max_total_time_minutes is not None:
        if recipe.prep_time_minutes is None or recipe.cook_time_minutes is None:
            time_incomplete = True
            reasons.append(RejectionReason.TIME_INCOMPLETE_WITH_CONSTRAINT)
        else:
            total_time = recipe.prep_time_minutes + recipe.cook_time_minutes
            if total_time > constraints.max_total_time_minutes:
                reasons.append(RejectionReason.MAX_TOTAL_TIME_EXCEEDED)

    # Budget enforcement. Incomplete cost is never treated as zero and
    # never hard-fails on its own -- it remains explicitly incomplete.
    cost_incomplete = not cost.price_complete
    if constraints.budget_aed is not None and cost.price_complete:
        assert cost.estimated_purchase_cost_aed is not None
        if cost.estimated_purchase_cost_aed > constraints.budget_aed:
            reasons.append(RejectionReason.BUDGET_EXCEEDED)

    return ConstraintEvaluationResult(
        hard_constraint_pass=len(reasons) == 0,
        rejection_reasons=tuple(reasons),
        time_incomplete=time_incomplete,
        cost_incomplete=cost_incomplete,
    )
