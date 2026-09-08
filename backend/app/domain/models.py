"""Shared provider-neutral domain models required by the deterministic core.

Mirrors TECHNICAL_SPEC.md section 8. Provider-specific fields must never
leak into these models (docs/AGENTS.md, docs/API_INTEGRATION_STANDARDS.md
section 28) -- adapters that do not exist yet in this ticket are
responsible for mapping vendor payloads into these shapes.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class NormalizationStatus(str, Enum):
    EXACT = "exact"
    ALIAS = "alias"
    UNKNOWN = "unknown"


class Difficulty(str, Enum):
    """Provider-grounded difficulty (Module E, FR-18/AC-20 UI display).

    Never inferred/calculated by Claude or by PantryPilot itself --
    parsed case-insensitively from the provider's own `difficulty`
    field (confirmed live on RecipeAPI.io, 2026-09-08: lowercase
    string values including "medium"/"hard"). Any value that is
    missing or does not match a known label maps to UNKNOWN rather
    than being silently guessed as EASY/MEDIUM.
    """

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    UNKNOWN = "unknown"

    @classmethod
    def from_raw(cls, raw: object) -> "Difficulty":
        if isinstance(raw, str):
            cleaned = raw.strip().lower()
            for member in cls:
                if member.value == cleaned:
                    return member
        return cls.UNKNOWN


class RecipeIngredient(BaseModel):
    model_config = ConfigDict(frozen=True)

    raw_name: str
    canonical_id: str | None = None
    raw_measure: str | None = None
    quantity: float | None = None
    normalized_unit: str | None = None
    optional: bool = False
    normalization_status: NormalizationStatus = NormalizationStatus.UNKNOWN


class Recipe(BaseModel):
    """Provider-neutral recipe DTO. Unique provenance key is
    (provider, provider_recipe_id)."""

    model_config = ConfigDict(frozen=True)

    id: str
    provider: str
    provider_recipe_id: str
    name: str
    cuisine: str | None = None
    category: str | None = None
    image_url: str | None = None
    ingredients: list[RecipeIngredient] = Field(default_factory=list)
    instructions: str | None = None
    source_url: str | None = None
    servings: int | None = None
    prep_time_minutes: int | None = None
    cook_time_minutes: int | None = None
    fetched_at: datetime | None = None
    # PP-002 addition (backward-compatible, optional, defaults preserve
    # PP-001 behavior for RecipeAPI.io-derived recipes): TECHNICAL_SPEC.md's
    # CuratedRecipe schema mandates explicit source_label/provenance_note
    # for every local curated recipe (DEC-003). The shared Recipe DTO had
    # no field to carry that, so these were added here rather than
    # inventing a parallel curated-only DTO that would defeat "same
    # internal Recipe DTO as RecipeAPI.io" (DEC-003).
    source_label: str | None = None
    provenance_note: str | None = None
    # Module E addition (backward-compatible, defaults to UNKNOWN so
    # every existing Recipe construction site remains valid).
    difficulty: Difficulty = Difficulty.UNKNOWN


class CostConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class CostEvaluation(BaseModel):
    """Deterministic cost-evaluation *input* to the ranker/constraint
    evaluator.

    This ticket does not implement the real grocery Cost Engine (M11) or
    Price Repository (M10). This type is the explicit, typed plug-point
    those later modules will populate, so the ranker/constraint design
    does not need to change when they land (per ticket cost rule).

    Unknown/incomplete cost must remain explicit: price_complete=False
    with estimated_purchase_cost_aed=None. It must never be coerced to
    zero (DEC-007, AR-12, AC-9).
    """

    model_config = ConfigDict(frozen=True)

    estimated_purchase_cost_aed: float | None = None
    price_complete: bool = False
    cost_confidence: CostConfidence = CostConfidence.UNKNOWN

    def model_post_init(self, __context: object) -> None:
        if self.price_complete and self.estimated_purchase_cost_aed is None:
            raise ValueError(
                "price_complete=True requires a non-null estimated_purchase_cost_aed"
            )
        if self.estimated_purchase_cost_aed is not None and self.estimated_purchase_cost_aed < 0:
            raise ValueError("estimated_purchase_cost_aed must not be negative")


CostEvaluation.UNKNOWN = CostEvaluation()  # type: ignore[attr-defined]


class RejectionReason(str, Enum):
    EXCLUDED_INGREDIENT_PRESENT = "excluded_ingredient_present"
    STRICT_CUISINE_MISMATCH = "strict_cuisine_mismatch"
    BUDGET_EXCEEDED = "budget_exceeded"
    # A budget was supplied but cost is incomplete/unknown with no
    # defensible conservative upper bound -- distinct from BUDGET_EXCEEDED
    # (a confirmed overage). Never implies the cost is treated as zero.
    BUDGET_INDETERMINATE_COST_INCOMPLETE = "budget_indeterminate_cost_incomplete"
    MAX_TOTAL_TIME_EXCEEDED = "max_total_time_exceeded"
    TIME_INCOMPLETE_WITH_CONSTRAINT = "time_incomplete_with_constraint"
    INSTRUCTIONS_UNUSABLE = "instructions_unusable"
    INGREDIENT_LIST_UNUSABLE = "ingredient_list_unusable"
    PROVENANCE_INVALID = "provenance_invalid"
    # Module E addition: user did not opt into Hard-difficulty recipes
    # (default filter is Easy+Medium only, per the search-form default).
    HARD_DIFFICULTY_EXCLUDED = "hard_difficulty_excluded"


class UserConstraints(BaseModel):
    """Normalized user constraints shared by the constraint evaluator
    and the ranker (budget, exclusions, cuisine, timing)."""

    model_config = ConfigDict(frozen=True)

    budget_aed: float | None = None
    excluded_canonical: frozenset[str] = Field(default_factory=frozenset)
    cuisine_preference: str | None = None
    cuisine_strict: bool = False
    max_total_time_minutes: int | None = None
    # Module E addition: default filter is Easy+Medium (True = Hard
    # allowed). Deterministic, evaluated in constraint_evaluator -- the
    # LLM has no authority over this field, matching how it has none
    # over budget/exclusions/cuisine strictness.
    allow_hard_difficulty: bool = False

    def model_post_init(self, __context: object) -> None:
        if self.budget_aed is not None and self.budget_aed < 0:
            raise ValueError("budget_aed must not be negative")
        if self.max_total_time_minutes is not None and self.max_total_time_minutes <= 0:
            raise ValueError("max_total_time_minutes must be positive")


class CandidateEvaluation(BaseModel):
    """Deterministic per-recipe evaluation result, matching the shape
    documented in TECHNICAL_SPEC.md section 8."""

    model_config = ConfigDict(frozen=True)

    recipe_id: str
    provider: str
    pantry_coverage: float
    matched_ingredients: list[str]
    missing_ingredients: list[str]
    missing_count: int
    unresolved_ingredients: list[str] = Field(default_factory=list)
    other_requirements: list[str] = Field(default_factory=list)
    estimated_purchase_cost_aed: float | None = None
    price_complete: bool = False
    cost_confidence: CostConfidence = CostConfidence.UNKNOWN
    cuisine_match: bool = False
    hard_constraint_pass: bool = False
    rejection_reasons: list[RejectionReason] = Field(default_factory=list)
    time_incomplete: bool = False
    deterministic_score: float | None = None
