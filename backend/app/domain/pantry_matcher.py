"""Deterministic pantry matching (M09 foundation).

Per TECHNICAL_SPEC.md section 12:
- required ingredient set is the unique canonical ingredient set;
- optional ingredients are excluded from the denominator;
- UNKNOWN ingredients never silently count as matches;
- duplicates resolving to one canonical ingredient count once;
- non-food "other requirements" are classified separately and do not
  count toward food coverage.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.canonical_ingredients import OTHER_REQUIREMENT_IDS
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

    required_canonical_ids = {
        ing.canonical_id
        for ing in recipe_ingredients
        if not ing.optional
        and ing.canonical_id is not None
        and ing.canonical_id not in other_requirement_ids
    }

    unresolved_ingredients = sorted(
        {ing.raw_name for ing in recipe_ingredients if ing.canonical_id is None}
    )

    matched = required_canonical_ids & pantry_canonical
    missing = required_canonical_ids - pantry_canonical

    total_required = len(required_canonical_ids)
    coverage = 1.0 if total_required == 0 else len(matched) / total_required

    return PantryMatchResult(
        matched_ingredients=tuple(sorted(matched)),
        missing_ingredients=tuple(sorted(missing)),
        missing_count=len(missing),
        pantry_coverage=coverage,
        unresolved_ingredients=tuple(unresolved_ingredients),
        other_requirements=tuple(other_requirements),
    )
