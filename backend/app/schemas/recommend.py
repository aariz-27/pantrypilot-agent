"""Module E: POST /api/recommend request/response DTOs.

Bounds follow TECHNICAL_SPEC.md section 15 and
docs/API_INTEGRATION_STANDARDS.md section 7/13, with two explicit
Module E overrides (ticket sections 8-9): `servings` and
`max_total_time_minutes` are now REQUIRED rather than optional.

Response DTOs expose only what the frontend needs (ticket section 29)
-- never a raw internal domain object, never a hidden LLM reasoning
trace, never a secret.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RecommendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")  # reject unknown/privileged fields (API standards section 8)

    ingredients: list[str] = Field(min_length=1, max_length=30)
    excluded_ingredients: list[str] = Field(default_factory=list, max_length=20)
    budget_aed: float | None = Field(default=None, ge=0, le=10000)
    cuisine: str | None = Field(default=None, min_length=1, max_length=50)
    cuisine_strict: bool = False
    servings: int = Field(ge=1, le=20)
    max_total_time_minutes: int = Field(ge=1, le=600)
    allow_hard_difficulty: bool = False

    @field_validator("ingredients", "excluded_ingredients")
    @classmethod
    def _validate_item_lengths(cls, value: list[str]) -> list[str]:
        cleaned = [v.strip() for v in value if v and v.strip()]
        for item in cleaned:
            if len(item) > 80:
                raise ValueError("each ingredient must be 1-80 characters")
        return cleaned


class MissingIngredientCost(BaseModel):
    raw_name: str
    canonical_id: str | None
    display_name: str
    normalized_unit: str | None
    scaled_required_quantity: float | None
    packages_needed: int | None
    estimated_cost_aed: float | None
    price_complete: bool
    cost_confidence: str


class UnresolvedIngredient(BaseModel):
    """A recipe ingredient the deterministic pipeline could not resolve
    to any canonical id (Priority-3, PR #15 correction pass,
    2026-09-08). `identity_key` is a deterministic, safe raw-text
    identity (app.domain.ingredient_normalizer.normalize_raw_text_identity)
    -- never a canonical_id -- used only so the frontend can match the
    SAME raw ingredient across multiple displayed cards when the user
    confirms they already own it."""

    raw_name: str
    display_name: str
    identity_key: str


class RecipeCard(BaseModel):
    recipe_id: str
    provider: str
    name: str
    image_url: str | None
    source_url: str | None
    cuisine: str | None
    difficulty: str
    requested_servings: int
    provider_original_servings: int | None
    servings_scaling_applied: bool
    prep_time_minutes: int | None
    cook_time_minutes: int | None
    total_time_minutes: int | None
    pantry_coverage: float
    matched_ingredients: list[str]
    missing_ingredients: list[MissingIngredientCost]
    unresolved_ingredients: list[UnresolvedIngredient]
    estimated_additional_spend_aed: float | None
    price_complete: bool
    cost_confidence: str
    instructions: str | None
    is_exact_match: bool
    deviation_reasons: list[str]
    # PR #15 second correction pass (2026-09-08): whether this card
    # contains the run's active anchor (the LLM's own most recent
    # primary search-anchor choice). None when no anchor was ever
    # defined for this run. Lets the frontend clearly label a reserve
    # candidate that only appears because the anchor-matching pool was
    # exhausted, instead of presenting it as an equally strong match.
    contains_active_anchor: bool | None = None


class RecommendResponse(BaseModel):
    request_id: str
    status: str
    search_attempts: int
    progress_events: list[str]
    pantry_unresolved: list[str]
    recommendations: list[RecipeCard]
    # Priority 4 (PR #15 correction pass, 2026-09-08): already-evaluated,
    # already-feasible candidates ranked below the top 3 -- never a hard-
    # rejected candidate (see closest_alternatives for those). Lets the
    # frontend reveal more good options with zero additional
    # RecipeAPI.io/Claude calls, since these were already retrieved and
    # evaluated during the normal bounded search.
    additional_options: list[RecipeCard] = Field(default_factory=list)
    closest_alternatives: list[RecipeCard]
    limitations: list[str]
    # Module E post-review addition (ticket section 3, PR #15): a
    # deterministic summary flag only -- never chain-of-thought, raw
    # agent actions, or internal prompts. True when some evaluated
    # candidate had better pantry coverage than what is shown here but
    # was hard-rejected specifically for exceeding max_total_time_minutes.
    higher_match_time_excluded: bool = False
    higher_match_time_excluded_count: int = 0
    higher_match_min_rejected_time_minutes: int | None = None
