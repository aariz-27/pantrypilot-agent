"""M11: deterministic missing-item purchase-cost engine.

Implements TECHNICAL_SPEC.md section 13's purchase-cost algorithm
exactly, producing app.domain.models.CostEvaluation objects that the
frozen PP-001 constraint evaluator/ranker already consume unchanged:

- at least one package for a required missing ingredient with a known
  package price;
- ceil(required/package) packages when the recipe's required quantity
  can be reliably normalized into the same unit dimension as the
  reference price;
- one conservative package, marked approximate (MEDIUM confidence),
  when the required quantity cannot be reliably normalized, or its
  unit dimension does not match the reference's -- never a fabricated
  cross-dimension (e.g. g<->ml) conversion;
- no price record for the canonical ID -> incomplete, never AED 0;
- only pantry-missing ingredients are costed at all -- this module
  never decides which ingredients are missing (that is
  app.domain.pantry_matcher's job, unchanged).

CostEvaluation/CostConfidence/evaluate_constraints/ranking weights are
all frozen PP-001 contracts and are not modified here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.domain.grocery_parsing import parse_package_content
from app.domain.models import CostConfidence, CostEvaluation, RecipeIngredient
from app.repositories.price_repository import PriceLookupResult, PriceRepository


@dataclass(frozen=True)
class IngredientCostDetail:
    """Per-ingredient breakdown, for callers that want more than the
    aggregate CostEvaluation (e.g. a future UI cost summary)."""

    canonical_id: str | None
    packages_needed: int | None
    package_price_aed: float | None
    line_cost_aed: float | None
    price_complete: bool
    cost_confidence: CostConfidence


def estimate_ingredient_cost(
    ingredient: RecipeIngredient, price_repository: PriceRepository
) -> IngredientCostDetail:
    """Estimate the purchase cost for ONE missing ingredient."""

    if ingredient.canonical_id is None:
        return IngredientCostDetail(None, None, None, None, False, CostConfidence.UNKNOWN)

    price = price_repository.get_price(ingredient.canonical_id)
    if price is None:
        return IngredientCostDetail(
            ingredient.canonical_id, None, None, None, False, CostConfidence.UNKNOWN
        )

    if (
        price.package_price_aed is None
        or price.normalized_package_quantity is None
        or price.normalized_package_quantity <= 0
    ):
        # We have a per-unit price but no concrete purchasable package
        # on record -- cannot compute a real purchase cost.
        return IngredientCostDetail(
            ingredient.canonical_id, None, None, None, False, CostConfidence.UNKNOWN
        )

    required = parse_package_content(ingredient.raw_measure)

    reliable = (
        required.normalized_unit is not None
        and required.normalized_total_quantity is not None
        and required.normalized_unit == price.normalized_unit
    )

    if not reliable:
        # Ambiguous/unsupported recipe measure (pinch, handful, to
        # taste, cup/tbsp/tsp, no measure at all) or an incompatible
        # unit dimension (e.g. recipe needs a piece count but the
        # reference is priced per gram). Conservative fallback: one
        # package, marked approximate -- never a fabricated conversion.
        return IngredientCostDetail(
            canonical_id=ingredient.canonical_id,
            packages_needed=1,
            package_price_aed=price.package_price_aed,
            line_cost_aed=round(price.package_price_aed, 2),
            price_complete=True,
            cost_confidence=CostConfidence.MEDIUM,
        )

    packages_needed = math.ceil(
        required.normalized_total_quantity / price.normalized_package_quantity
    )
    packages_needed = max(1, packages_needed)
    line_cost = round(packages_needed * price.package_price_aed, 2)

    return IngredientCostDetail(
        canonical_id=ingredient.canonical_id,
        packages_needed=packages_needed,
        package_price_aed=price.package_price_aed,
        line_cost_aed=line_cost,
        price_complete=True,
        cost_confidence=CostConfidence.HIGH,
    )


_CONFIDENCE_RANK = {
    CostConfidence.HIGH: 0,
    CostConfidence.MEDIUM: 1,
    CostConfidence.LOW: 2,
    CostConfidence.UNKNOWN: 3,
}


def estimate_purchase_cost(
    missing_ingredients: list[RecipeIngredient], price_repository: PriceRepository
) -> CostEvaluation:
    """Aggregate purchase-cost estimate across all pantry-missing
    ingredients for one recipe candidate. Only pantry-missing
    ingredients should be passed in -- callers (e.g. the future
    candidate-evaluation composition) are responsible for that
    filtering via app.domain.pantry_matcher, unchanged here.

    Incomplete if ANY missing ingredient lacks a usable price -- a
    candidate's total cost is never "complete" while one of its
    required purchases is unknown; that unknown is never treated as
    zero.
    """

    if not missing_ingredients:
        return CostEvaluation(
            estimated_purchase_cost_aed=0.0, price_complete=True, cost_confidence=CostConfidence.HIGH
        )

    details = [estimate_ingredient_cost(ing, price_repository) for ing in missing_ingredients]

    if any(not d.price_complete for d in details):
        return CostEvaluation()  # incomplete -- never coerced to zero or a partial sum

    total = round(sum(d.line_cost_aed for d in details), 2)
    worst_confidence = max((d.cost_confidence for d in details), key=lambda c: _CONFIDENCE_RANK[c])

    return CostEvaluation(
        estimated_purchase_cost_aed=total,
        price_complete=True,
        cost_confidence=worst_confidence,
    )
