"""Module E: pure, deterministic mapping from AgentResult/CandidateEvaluation
into the public RecommendResponse contract.

No LLM call, no I/O, no new business rule -- only presentation-layer
formatting and filtering of values Modules A-D already computed
deterministically. Kept separate from app.api.recommend so it is
independently unit-testable without spinning up FastAPI/httpx.
"""

from __future__ import annotations

from app.agent.orchestrator import AgentResult
from app.domain.ingredient_autocomplete import humanize_canonical_id
from app.domain.ingredient_normalizer import normalize_raw_text_identity
from app.domain.models import CandidateEvaluation, RejectionReason
from app.schemas.recommend import MissingIngredientCost, RecipeCard, RecommendResponse, UnresolvedIngredient

# Rejection reasons that represent a flexible target (time/budget) a
# "closest alternative" may legitimately exceed, per ticket section 18.
_FLEXIBLE_REJECTION_REASONS = frozenset(
    {
        RejectionReason.MAX_TOTAL_TIME_EXCEEDED,
        RejectionReason.TIME_INCOMPLETE_WITH_CONSTRAINT,
        RejectionReason.BUDGET_EXCEEDED,
        RejectionReason.BUDGET_INDETERMINATE_COST_INCOMPLETE,
    }
)


def _display_name(raw_name: str, canonical_id: str | None) -> str:
    return humanize_canonical_id(canonical_id) if canonical_id else raw_name


def _is_never_relax_violation(candidate: CandidateEvaluation) -> bool:
    """True if this candidate's rejection includes a rule that must
    never be relaxed even for a 'closest alternative' (ticket section
    18): excluded ingredient, strict cuisine mismatch, invalid/unusable
    data, or the Hard-difficulty filter."""

    return any(reason not in _FLEXIBLE_REJECTION_REASONS for reason in candidate.rejection_reasons)


def _deviation_reasons(
    candidate: CandidateEvaluation,
    recipe,
    max_total_time_minutes: int | None,
    budget_aed: float | None,
    *,
    cuisine_preference: str | None = None,
    scaling=None,
) -> list[str]:
    reasons: list[str] = []
    if RejectionReason.MAX_TOTAL_TIME_EXCEEDED in candidate.rejection_reasons:
        if (
            max_total_time_minutes is not None
            and recipe.prep_time_minutes is not None
            and recipe.cook_time_minutes is not None
        ):
            over = (recipe.prep_time_minutes + recipe.cook_time_minutes) - max_total_time_minutes
            if over > 0:
                reasons.append(f"{over} min over your target")
    elif RejectionReason.TIME_INCOMPLETE_WITH_CONSTRAINT in candidate.rejection_reasons:
        # 2026-09-13 recommendation-behavior fix: this candidate is now
        # shown (previously it was simply hard-rejected and dropped) --
        # honestly label that its time fit could not be confirmed,
        # never silently imply it satisfies the selected time.
        reasons.append("Cook time not confirmed")

    if RejectionReason.BUDGET_EXCEEDED in candidate.rejection_reasons:
        if budget_aed is not None and candidate.price_complete and candidate.estimated_purchase_cost_aed is not None:
            over = candidate.estimated_purchase_cost_aed - budget_aed
            if over > 0:
                reasons.append(f"Est. AED {over:.2f} over budget")
    elif RejectionReason.BUDGET_INDETERMINATE_COST_INCOMPLETE in candidate.rejection_reasons:
        # DEC-007: unknown price is never treated as zero -- label it
        # honestly rather than silently claiming the budget is met.
        reasons.append("Price unknown")

    # 2026-09-13 recommendation-behavior fix (soft preferences, ticket's
    # "PRODUCT BEHAVIOR" section): non-strict cuisine and servings never
    # reject a candidate (unchanged), but a mismatch is worth a plain,
    # honest label when this candidate is being shown as an alternative
    # rather than an exact preference match. The card's own `cuisine`
    # field already shows the actual cuisine, so the label itself stays
    # generic.
    if cuisine_preference:
        recipe_cuisine = (recipe.cuisine or "").strip().lower()
        if recipe_cuisine and recipe_cuisine != cuisine_preference.strip().lower():
            reasons.append("Different cuisine")

    if scaling is not None and scaling.original_servings is not None and scaling.original_servings != scaling.requested_servings:
        reasons.append(f"Serves {scaling.original_servings}; can be scaled")

    return reasons


def build_unresolved_ingredient(raw_name: str) -> UnresolvedIngredient:
    return UnresolvedIngredient(
        raw_name=raw_name,
        display_name=raw_name,
        identity_key=normalize_raw_text_identity(raw_name),
    )


def build_missing_ingredient_cost(breakdown_row) -> MissingIngredientCost:
    detail = breakdown_row.detail
    return MissingIngredientCost(
        raw_name=breakdown_row.raw_name,
        canonical_id=breakdown_row.canonical_id,
        display_name=_display_name(breakdown_row.raw_name, breakdown_row.canonical_id),
        normalized_unit=breakdown_row.normalized_unit,
        scaled_required_quantity=breakdown_row.scaled_required_quantity,
        packages_needed=detail.packages_needed,
        estimated_cost_aed=detail.line_cost_aed,
        price_complete=detail.price_complete,
        cost_confidence=detail.cost_confidence.value,
    )


def build_recipe_card(
    candidate: CandidateEvaluation,
    result: AgentResult,
    *,
    is_exact_match: bool,
    max_total_time_minutes: int | None,
    budget_aed: float | None,
    cuisine_preference: str | None = None,
) -> RecipeCard | None:
    recipe = result.recipe_by_id.get(candidate.recipe_id)
    if recipe is None:
        return None

    scaling = result.scaling_by_id.get(candidate.recipe_id)
    breakdown = result.missing_breakdown_by_id.get(candidate.recipe_id, [])

    total_time_minutes = None
    if recipe.prep_time_minutes is not None and recipe.cook_time_minutes is not None:
        total_time_minutes = recipe.prep_time_minutes + recipe.cook_time_minutes

    return RecipeCard(
        recipe_id=candidate.recipe_id,
        provider=candidate.provider,
        name=recipe.name,
        image_url=recipe.image_url,
        source_url=recipe.source_url,
        cuisine=recipe.cuisine,
        difficulty=recipe.difficulty.value,
        requested_servings=scaling.requested_servings if scaling else recipe.servings or 0,
        provider_original_servings=scaling.original_servings if scaling else recipe.servings,
        servings_scaling_applied=bool(scaling and scaling.scaling_applied and scaling.scaling_factor != 1.0),
        prep_time_minutes=recipe.prep_time_minutes,
        cook_time_minutes=recipe.cook_time_minutes,
        total_time_minutes=total_time_minutes,
        pantry_coverage=candidate.pantry_coverage,
        matched_ingredients=[humanize_canonical_id(cid) for cid in candidate.matched_ingredients],
        missing_ingredients=[build_missing_ingredient_cost(row) for row in breakdown],
        unresolved_ingredients=[build_unresolved_ingredient(name) for name in candidate.unresolved_ingredients],
        estimated_additional_spend_aed=candidate.estimated_purchase_cost_aed,
        price_complete=candidate.price_complete,
        cost_confidence=candidate.cost_confidence.value,
        instructions=recipe.instructions,
        is_exact_match=is_exact_match,
        contains_active_anchor=result.anchor_match_by_id.get(candidate.recipe_id),
        deviation_reasons=(
            []
            if is_exact_match
            else _deviation_reasons(
                candidate, recipe, max_total_time_minutes, budget_aed,
                cuisine_preference=cuisine_preference, scaling=scaling,
            )
        ),
    )


def build_recommend_response(
    result: AgentResult,
    *,
    max_total_time_minutes: int | None,
    budget_aed: float | None,
    cuisine_preference: str | None = None,
) -> RecommendResponse:
    recommendations = []
    for c in result.recommendations:
        card = build_recipe_card(
            c, result, is_exact_match=True, max_total_time_minutes=max_total_time_minutes, budget_aed=budget_aed
        )
        if card is not None:
            recommendations.append(card)

    # Priority 4 (PR #15 correction pass, 2026-09-08): additional_options
    # are drawn from the SAME hard-constraint-passing pool as
    # recommendations (is_exact_match=True is correct for them too --
    # they differ from recommendations only by rank position, never by
    # constraint outcome), so they get the identical, unmodified mapping
    # path recommendations already use.
    additional_options = []
    for c in result.additional_options:
        card = build_recipe_card(
            c, result, is_exact_match=True, max_total_time_minutes=max_total_time_minutes, budget_aed=budget_aed
        )
        if card is not None:
            additional_options.append(card)

    closest_alternatives = []
    for c in result.closest_alternatives:
        if _is_never_relax_violation(c):
            # Never present a hard-safety violation (exclusion, strict
            # cuisine mismatch, unusable/invalid data, disallowed Hard
            # difficulty) as a "closest alternative" -- ticket section 18.
            continue
        card = build_recipe_card(
            c, result, is_exact_match=False, max_total_time_minutes=max_total_time_minutes, budget_aed=budget_aed,
            cuisine_preference=cuisine_preference,
        )
        if card is not None:
            closest_alternatives.append(card)

    limitations: list[str] = []
    if result.status == "no_feasible_match" and not closest_alternatives:
        limitations.append("No recipes matched your criteria closely enough to show, even as alternatives.")
    if result.pantry_unresolved:
        limitations.append(
            f"{len(result.pantry_unresolved)} pantry ingredient(s) were not recognized and were not used in the search."
        )

    return RecommendResponse(
        request_id=result.request_id,
        status=result.status,
        search_attempts=result.search_attempts,
        progress_events=result.progress_events,
        pantry_unresolved=result.pantry_unresolved,
        recommendations=recommendations,
        additional_options=additional_options,
        closest_alternatives=closest_alternatives,
        limitations=limitations,
        higher_match_time_excluded=result.higher_match_time_excluded,
        higher_match_time_excluded_count=result.higher_match_time_excluded_count,
        higher_match_min_rejected_time_minutes=result.higher_match_min_rejected_time_minutes,
    )
