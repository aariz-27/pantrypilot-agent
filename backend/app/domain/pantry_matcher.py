"""Deterministic pantry matching (M09 foundation).

Per TECHNICAL_SPEC.md section 12:
- required ingredient set is the unique canonical ingredient set;
- optional ingredients are excluded from the denominator;
- UNKNOWN ingredients never silently count as matches;
- duplicates resolving to one canonical ingredient count once;
- non-food "other requirements" are classified separately and do not
  count toward food coverage.

Per TECHNICAL_SPEC.md section 11: "UNKNOWN recipe ingredients remain
visible but are not assumed matched and reduce coverage/cost
completeness." A required (non-optional) ingredient that failed
normalization therefore still enters the pantry-coverage denominator
(it can never be satisfied, since it has no canonical identity to
compare against the pantry) while never entering the numerator and
never being fabricated a canonical ID. It is reported only in
`unresolved_ingredients` -- never folded into `missing_ingredients`,
which remains canonical-ID-only for downstream (cost/display) use.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# PR #15 non-food wiring fix (2026-09-09): imports from
# app.domain.grocery_taxonomy, not app.domain.canonical_ingredients --
# grocery_taxonomy is the vocabulary every real production normalization
# call site actually uses (see its own OTHER_REQUIREMENT_IDS docstring),
# so this default must reference the SAME ids a recipe ingredient can
# actually resolve to, or "other requirement" exclusion here would filter
# against ids that could never appear in practice.
from app.domain.grocery_taxonomy import OTHER_REQUIREMENT_IDS
from app.domain.models import RecipeIngredient


@dataclass(frozen=True)
class PantryMatchResult:
    matched_ingredients: tuple[str, ...]
    missing_ingredients: tuple[str, ...]
    missing_count: int
    pantry_coverage: float
    unresolved_ingredients: tuple[str, ...] = field(default_factory=tuple)
    other_requirements: tuple[str, ...] = field(default_factory=tuple)


def match_pantry(
    pantry_canonical: frozenset[str],
    recipe_ingredients: list[RecipeIngredient],
    other_requirement_ids: frozenset[str] = OTHER_REQUIREMENT_IDS,
) -> PantryMatchResult:
    other_requirements = sorted(
        {
            ing.canonical_id
            for ing in recipe_ingredients
            if ing.canonical_id is not None and ing.canonical_id in other_requirement_ids
        }
    )

    required_resolved_ids = {
        ing.canonical_id
        for ing in recipe_ingredients
        if not ing.optional
        and ing.canonical_id is not None
        and ing.canonical_id not in other_requirement_ids
    }

    # Required ingredients that failed normalization have no canonical
    # identity, so they cannot be added to required_resolved_ids or
    # matched against the pantry set. They are still real required
    # ingredients, so they must still count in the coverage denominator
    # (never the numerator). Deduplicated by cleaned raw text so that
    # the same unresolved ingredient repeated across recipe lines still
    # counts once, mirroring the canonical dedup rule above.
    required_unresolved_keys = {
        ing.raw_name.strip().lower()
        for ing in recipe_ingredients
        if not ing.optional and ing.canonical_id is None
    }

    unresolved_ingredients = sorted(
        {ing.raw_name for ing in recipe_ingredients if ing.canonical_id is None}
    )

    matched = required_resolved_ids & pantry_canonical
    missing = required_resolved_ids - pantry_canonical

    total_required = len(required_resolved_ids) + len(required_unresolved_keys)
    coverage = 1.0 if total_required == 0 else len(matched) / total_required

    return PantryMatchResult(
        matched_ingredients=tuple(sorted(matched)),
        missing_ingredients=tuple(sorted(missing)),
        missing_count=len(missing),
        pantry_coverage=coverage,
        unresolved_ingredients=tuple(unresolved_ingredients),
        other_requirements=tuple(other_requirements),
    )
