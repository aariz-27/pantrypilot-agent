"""Deterministic tool facade the orchestrator calls (ticket section 10).

Composes the existing, frozen Module A/B/C pipeline --

    recipe retrieval -> ingredient normalization -> pantry matching
    -> missing ingredients -> price lookup -> purchase cost
    -> hard constraints -> deterministic ranking

-- exactly as already proven in
tests/integration/test_module_a_b_c_integration.py. This module never
reimplements any of that logic; it only sequences calls to it and maps
provider-layer typed errors into a small outcome shape the orchestrator
can turn into an observation.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.candidate_evaluation import evaluate_candidate
from app.domain.cost_engine import estimate_purchase_cost
from app.domain.grocery_taxonomy import (
    CANONICAL_GROCERY_INGREDIENTS,
    OTHER_REQUIREMENT_IDS,
    RECIPE_INGREDIENT_ALIASES,
)
from app.domain.ingredient_normalizer import normalize_ingredient_name
from app.domain.models import CandidateEvaluation, Recipe, UserConstraints
from app.domain.provider_errors import (
    RecipeProviderConfigurationError,
    RecipeProviderError,
    RecipeProviderMalformedResponseError,
    RecipeProviderRateLimitedError,
    RecipeProviderTimeoutError,
    RecipeProviderUnavailableError,
)
from app.domain.ranker import rank_candidates
from app.recipe.provider import RecipeProvider, SearchResultItem, SearchStrategy
from app.repositories.price_repository import PriceRepository

# Cuisines for which the local curated provider is an approved regional
# route (DEC-003). Matched case-insensitively against either the
# requested search cuisine or the user's overall cuisine preference.
APPROVED_LOCAL_CURATED_CUISINES = frozenset({"indian", "pakistani", "desi"})

_ERROR_CATEGORY_BY_EXCEPTION = {
    RecipeProviderTimeoutError: "timeout",
    RecipeProviderRateLimitedError: "rate_limited",
    RecipeProviderUnavailableError: "unavailable",
    RecipeProviderConfigurationError: "configuration_error",
    RecipeProviderMalformedResponseError: "malformed_response",
}

TRANSIENT_ERROR_CATEGORIES = frozenset({"timeout", "unavailable", "rate_limited"})


def is_approved_local_curated_intent(*cuisines: str | None) -> bool:
    for cuisine in cuisines:
        if cuisine and cuisine.strip().lower() in APPROVED_LOCAL_CURATED_CUISINES:
            return True
    return False


@dataclass(frozen=True)
class ProviderSearchOutcome:
    items: tuple[SearchResultItem, ...]
    has_more: bool
    error_category: str | None  # None means success


async def execute_search(
    provider: RecipeProvider | None, strategy: SearchStrategy
) -> ProviderSearchOutcome:
    if provider is None:
        return ProviderSearchOutcome(items=(), has_more=False, error_category="configuration_error")
    try:
        result = await provider.search(strategy)
    except RecipeProviderError as exc:
        category = next(
            (cat for exc_type, cat in _ERROR_CATEGORY_BY_EXCEPTION.items() if isinstance(exc, exc_type)),
            "unavailable",
        )
        return ProviderSearchOutcome(items=(), has_more=False, error_category=category)
    return ProviderSearchOutcome(items=tuple(result.items), has_more=result.has_more, error_category=None)


async def fetch_recipe_details(
    provider: RecipeProvider, items: list[SearchResultItem]
) -> tuple[list[Recipe], list[str]]:
    """Fetch full recipe detail for each search-result item. An
    individual malformed/not-found recipe is skipped (its id recorded),
    rather than failing the whole batch -- consistent with M07's
    listing-vs-detail strictness split.

    Priority-1 efficiency fix (PR #15 correction pass, 2026-09-08): when
    a search-result item already carries `full_recipe` (the provider's
    search/list response already contained the complete recipe -- see
    RecipeAPIIOAdapter._try_map_full_recipe_from_list_item), that Recipe
    is used directly and no separate get_details() network round trip
    is made for it. This is the same grounded, provider-mapped Recipe
    object either way -- never a different mapping path -- so this is a
    pure request-count optimization, not a groundedness change. Any
    item without a usable full_recipe falls back to get_details()
    exactly as before."""

    recipes: list[Recipe] = []
    failed_ids: list[str] = []
    for item in items:
        if item.full_recipe is not None:
            recipes.append(item.full_recipe)
            continue
        try:
            recipes.append(await provider.get_details(item.provider_recipe_id))
        except RecipeProviderError:
            failed_ids.append(item.id)
    return recipes, failed_ids


def normalize_recipe_ingredients(recipe: Recipe) -> Recipe:
    """M08 canonical resolution, applied with the same grocery-taxonomy
    vocabulary the pricing layer uses, so recipe-side and pantry-side
    canonical IDs correlate (proven pattern from
    test_module_a_b_c_integration.py)."""

    normalized = []
    for ing in recipe.ingredients:
        result = normalize_ingredient_name(
            ing.raw_name, canonical_vocabulary=CANONICAL_GROCERY_INGREDIENTS, aliases=RECIPE_INGREDIENT_ALIASES
        )
        normalized.append(
            ing.model_copy(update={"canonical_id": result.canonical_id, "normalization_status": result.status})
        )
    return recipe.model_copy(update={"ingredients": normalized})


def evaluate_recipe(
    recipe: Recipe,
    pantry_canonical: frozenset[str],
    constraints: UserConstraints,
    price_repository: PriceRepository,
) -> CandidateEvaluation:
    """M08 -> M09 -> M10 -> M11 -> M12 for one grounded recipe."""

    normalized = normalize_recipe_ingredients(recipe)
    # PR #15 non-food wiring fix (2026-09-09): a non-food "other
    # requirement" (e.g. parchment_paper, cedar_plank) must never enter
    # cost estimation -- app.domain.pantry_matcher.match_pantry already
    # excludes these from ITS OWN missing_ingredients/coverage
    # computation, but this function computes missing_canonical
    # independently (for cost purposes only) and previously had no
    # matching exclusion, so an other-requirement ingredient would
    # silently be treated as an unpriced FOOD ingredient here -- costed
    # as "missing", contaminating price_complete/cost_confidence for the
    # whole candidate. estimate_purchase_cost's own docstring already
    # says callers must filter via pantry_matcher; this now actually
    # does so, using the exact same OTHER_REQUIREMENT_IDS set.
    missing_canonical = {
        ing.canonical_id
        for ing in normalized.ingredients
        if ing.canonical_id is not None
        and ing.canonical_id not in pantry_canonical
        and ing.canonical_id not in OTHER_REQUIREMENT_IDS
    }
    missing_ingredients = [ing for ing in normalized.ingredients if ing.canonical_id in missing_canonical]
    cost = estimate_purchase_cost(missing_ingredients, price_repository)
    return evaluate_candidate(normalized, pantry_canonical, constraints, cost)


def evaluate_and_rank(
    recipes: list[Recipe],
    pantry_canonical: frozenset[str],
    constraints: UserConstraints,
    price_repository: PriceRepository,
) -> tuple[list[CandidateEvaluation], list[CandidateEvaluation]]:
    """Returns (feasible, rejected). Feasible candidates are M13-ranked;
    rejected candidates are returned in evaluation order for the
    "closest alternatives" report -- ranking is only defined for
    already-feasible candidates (M13's own contract)."""

    all_evaluations = [evaluate_recipe(r, pantry_canonical, constraints, price_repository) for r in recipes]
    feasible = [e for e in all_evaluations if e.hard_constraint_pass]
    rejected = [e for e in all_evaluations if not e.hard_constraint_pass]

    if feasible:
        cuisine_by_id = {r.id: r.cuisine for r in recipes}
        name_by_id = {r.id: r.name for r in recipes}
        feasible = rank_candidates(feasible, constraints, cuisine_by_id, name_by_id)

    return feasible, rejected
