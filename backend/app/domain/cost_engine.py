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
from app.repositories.price_repository import PriceRepository


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

    return _estimate_canonical_group_cost([ingredient], price_repository)


def _estimate_canonical_group_cost(
    ingredients: list[RecipeIngredient], price_repository: PriceRepository
) -> IngredientCostDetail:
    """Estimate the purchase cost for every recipe line that resolves to
    ONE canonical ingredient, combined.

    A recipe may legitimately list the same missing ingredient across
    more than one line (e.g. "salt to taste" and "1 tsp salt for the
    marinade", or two separate "onion" lines for different parts of the
    method). Costing each line independently would buy a separate
    package per line instead of covering the ingredient's one real
    combined requirement -- audit finding (2026-09-07), fixed here.
    All lines in `ingredients` must share the same canonical_id (or all
    be None); callers group by canonical_id before calling this.
    """

    canonical_id = ingredients[0].canonical_id
    if canonical_id is None:
        return IngredientCostDetail(None, None, None, None, False, CostConfidence.UNKNOWN)

    price = price_repository.get_price(canonical_id)
    if price is None:
        return IngredientCostDetail(canonical_id, None, None, None, False, CostConfidence.UNKNOWN)

    if (
        price.package_price_aed is None
        or price.normalized_package_quantity is None
        or price.normalized_package_quantity <= 0
    ):
        # We have a per-unit price but no concrete purchasable package
        # on record -- cannot compute a real purchase cost.
        return IngredientCostDetail(canonical_id, None, None, None, False, CostConfidence.UNKNOWN)

    parsed_lines = [parse_package_content(ing.raw_measure) for ing in ingredients]
    reliable_quantities = [
        parsed.normalized_total_quantity
        for parsed in parsed_lines
        if parsed.normalized_unit is not None
        and parsed.normalized_total_quantity is not None
        and parsed.normalized_unit == price.normalized_unit
    ]

    if not reliable_quantities:
        # Zero lines have a reliable compatible quantity (ambiguous/
        # unsupported measure -- pinch, handful, to taste, cup/tbsp/tsp
        # -- or an incompatible unit dimension on every line). Never
        # fabricate a conversion or a quantity. Conservative fallback:
        # one package total for this ingredient, marked approximate.
        return IngredientCostDetail(
            canonical_id=canonical_id,
            packages_needed=1,
            package_price_aed=price.package_price_aed,
            line_cost_aed=round(price.package_price_aed, 2),
            price_complete=True,
            cost_confidence=CostConfidence.MEDIUM,
        )

    # At least one line has a known, unit-compatible quantity. Sum only
    # those reliable quantities -- never the ambiguous/incompatible
    # ones, and never a guessed value for them -- to get the known
    # minimum this ingredient definitely requires.
    total_reliable = sum(reliable_quantities)
    known_min_packages = max(1, math.ceil(total_reliable / price.normalized_package_quantity))

    if len(reliable_quantities) == len(parsed_lines):
        # Every line was reliable: the known minimum is the exact
        # answer, not just a floor.
        packages_needed = known_min_packages
        cost_confidence = CostConfidence.HIGH
    else:
        # One or more lines are ambiguous/unsupported/incompatible.
        # Their real quantity is unknown, so it can only ever add
        # uncertainty on top of the known minimum -- it must never be
        # used to fabricate an addition, but it must also never let the
        # result fall below the package count the reliable lines have
        # already proven necessary (audit correction, 2026-09-07: the
        # previous fallback discarded the reliable subtotal entirely
        # whenever any line was ambiguous, which could undercost a
        # known minimum requirement -- e.g. "1500 g" + "a pinch" used to
        # return 1 package instead of the 2 packages "1500 g" alone
        # already requires).
        packages_needed = known_min_packages
        cost_confidence = CostConfidence.MEDIUM

    line_cost = round(packages_needed * price.package_price_aed, 2)

    return IngredientCostDetail(
        canonical_id=canonical_id,
        packages_needed=packages_needed,
        package_price_aed=price.package_price_aed,
        line_cost_aed=line_cost,
        price_complete=True,
        cost_confidence=cost_confidence,
    )


_CONFIDENCE_RANK = {
    CostConfidence.HIGH: 0,
    CostConfidence.MEDIUM: 1,
    CostConfidence.LOW: 2,
    CostConfidence.UNKNOWN: 3,
}


@dataclass(frozen=True)
class MissingIngredientBreakdown:
    """Module E: one row per missing canonical ingredient, for the
    ingredient-level cost display (ticket section 23). Reuses the exact
    same grouping/costing logic as estimate_purchase_cost() -- this is
    additive plumbing, not a new pricing rule."""

    raw_name: str
    canonical_id: str | None
    normalized_unit: str | None
    scaled_required_quantity: float | None
    detail: IngredientCostDetail


def estimate_missing_ingredient_breakdown(
    missing_ingredients: list[RecipeIngredient], price_repository: PriceRepository
) -> list[MissingIngredientBreakdown]:
    """Per-ingredient breakdown for the missing ingredients of one
    recipe candidate, grouped by canonical ID exactly as
    estimate_purchase_cost() groups them (same combined-requirement
    rule), but returning one row per group instead of only the
    aggregate. `raw_name` is the first-seen raw ingredient text in the
    group, for display only -- never used for pricing identity."""

    groups: dict[str | None, list[RecipeIngredient]] = {}
    group_order: list[str | None] = []
    for ing in missing_ingredients:
        if ing.canonical_id not in groups:
            groups[ing.canonical_id] = []
            group_order.append(ing.canonical_id)
        groups[ing.canonical_id].append(ing)

    rows: list[MissingIngredientBreakdown] = []
    for key in group_order:
        group = groups[key]
        detail = _estimate_canonical_group_cost(group, price_repository)
        parsed_lines = [parse_package_content(ing.raw_measure) for ing in group]
        reliable = [
            p.normalized_total_quantity
            for p in parsed_lines
            if p.normalized_unit is not None and p.normalized_total_quantity is not None
        ]
        unit = next((p.normalized_unit for p in parsed_lines if p.normalized_unit is not None), None)
        total_reliable = round(sum(reliable), 4) if reliable else None

        rows.append(
            MissingIngredientBreakdown(
                raw_name=group[0].raw_name,
                canonical_id=key,
                normalized_unit=unit,
                scaled_required_quantity=total_reliable,
                detail=detail,
            )
        )

    return rows


def estimate_purchase_cost(
    missing_ingredients: list[RecipeIngredient], price_repository: PriceRepository
) -> CostEvaluation:
    """Aggregate purchase-cost estimate across all pantry-missing
    ingredients for one recipe candidate. Only pantry-missing
    ingredients should be passed in -- callers (e.g. the future
    candidate-evaluation composition) are responsible for that
    filtering via app.domain.pantry_matcher, unchanged here.

    A recipe may list the same missing canonical ingredient on more
    than one line (e.g. "salt to taste" and "1 tsp salt for the
    marinade"); these are grouped and costed together as one combined
    requirement rather than once per line, so the estimate never buys
    more separate packages than the recipe actually needs (audit
    finding, 2026-09-07). Grouping preserves first-seen order for
    deterministic output.

    Incomplete if ANY missing ingredient lacks a usable price -- a
    candidate's total cost is never "complete" while one of its
    required purchases is unknown; that unknown is never treated as
    zero.
    """

    if not missing_ingredients:
        return CostEvaluation(
            estimated_purchase_cost_aed=0.0, price_complete=True, cost_confidence=CostConfidence.HIGH
        )

    groups: dict[str | None, list[RecipeIngredient]] = {}
    group_order: list[str | None] = []
    for ing in missing_ingredients:
        if ing.canonical_id not in groups:
            groups[ing.canonical_id] = []
            group_order.append(ing.canonical_id)
        groups[ing.canonical_id].append(ing)

    details = [_estimate_canonical_group_cost(groups[key], price_repository) for key in group_order]

    if any(not d.price_complete for d in details):
        return CostEvaluation()  # incomplete -- never coerced to zero or a partial sum

    total = round(sum(d.line_cost_aed for d in details), 2)
    worst_confidence = max((d.cost_confidence for d in details), key=lambda c: _CONFIDENCE_RANK[c])

    return CostEvaluation(
        estimated_purchase_cost_aed=total,
        price_complete=True,
        cost_confidence=worst_confidence,
    )
