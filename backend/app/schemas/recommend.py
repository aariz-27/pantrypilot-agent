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
    unresolved_ingredients: list[str]
    estimated_additional_spend_aed: float | None
    price_complete: bool
    cost_confidence: str
    instructions: str | None
    is_exact_match: bool
    deviation_reasons: list[str]


class RecommendResponse(BaseModel):
    request_id: str
    status: str
    search_attempts: int
    progress_events: list[str]
    pantry_unresolved: list[str]
    recommendations: list[RecipeCard]
    closest_alternatives: list[RecipeCard]
    limitations: list[str]
