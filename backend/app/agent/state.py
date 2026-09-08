"""Typed Module D agent state (TECHNICAL_SPEC.md section 4, "Agent state").

A plain mutable dataclass, matching the existing codebase convention of
dataclasses for internal engine state (PantryMatchResult,
ConstraintEvaluationResult) versus frozen pydantic models for wire-level
contracts. Mutation happens only through the explicit methods below, so
every state transition is testable. No hidden chain-of-thought is ever
stored here -- only high-level structured progress strings and typed
counters/results (ticket section 6, section 20).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.cost_engine import MissingIngredientBreakdown
from app.domain.models import CandidateEvaluation, Recipe
from app.domain.serving_scaler import ScaledRecipe
from app.recipe.provider import SearchStrategy

MAX_SEARCH_ATTEMPTS = 3
MAX_EVALUATED_CANDIDATES = 20
MAX_FINAL_RECOMMENDATIONS = 3
MAX_CORRECTIVE_RETRIES_PER_STEP = 1


@dataclass(frozen=True)
class SearchAttemptRecord:
    """One executed search/paginate/retry round-trip, for audit and for
    the "materially different strategy" / "transient retry only"
    policy checks in app.agent.tools."""

    route: str
    strategy: SearchStrategy
    outcome: str  # "ok" | "timeout" | "unavailable" | "rate_limited" | "malformed_response" | "configuration_error"
    has_more: bool = False


@dataclass
class AgentState:
    request_id: str
    pantry_raw: list[str]
    pantry_canonical: frozenset[str]
    budget_aed: float | None
    cuisine_preference: str | None
    cuisine_strict: bool
    servings: int
    max_total_time_minutes: int | None
    excluded_raw: list[str]
    excluded_canonical: frozenset[str]
    # Module E: raw pantry text that failed canonical normalization,
    # for the API layer to surface as "Unrecognized" -- never silently
    # promoted into the canonical taxonomy or pricing tables.
    pantry_unresolved: tuple[str, ...] = field(default_factory=tuple)

    search_attempts: int = 0
    max_search_attempts: int = MAX_SEARCH_ATTEMPTS
    searched_strategies: list[SearchAttemptRecord] = field(default_factory=list)
    distinct_search_signatures: set[tuple] = field(default_factory=set)
    # Recipe identity, matching app.recipe.provider.dedupe_search_results'
    # own contract exactly: (provider, provider_recipe_id) tuples built
    # directly from SearchResultItem/Recipe's own structured fields --
    # never derived by parsing the composite `id` string, which would
    # make correctness depend on provider name literals never colliding
    # under string concatenation (independent review finding, 2026-09-07).
    candidate_ids_seen: set[tuple[str, str]] = field(default_factory=set)
    evaluated_candidates: list[CandidateEvaluation] = field(default_factory=list)
    recipe_meta_by_id: dict[str, tuple[str | None, str]] = field(default_factory=dict)
    best_feasible: list[CandidateEvaluation] = field(default_factory=list)
    provider_status: dict[str, str] = field(default_factory=dict)
    # Module E additions: user-facing detail carried alongside the
    # frozen CandidateEvaluation contract, keyed by recipe_id. Populated
    # deterministically in AgentOrchestrator._run_attempt -- never by
    # the LLM. recipe_by_id holds the NORMALIZED + SERVING-SCALED
    # recipe (ingredients only; servings/prep/cook/instructions/etc.
    # untouched), for the API layer to build cards/detail views from.
    recipe_by_id: dict[str, Recipe] = field(default_factory=dict)
    scaling_by_id: dict[str, ScaledRecipe] = field(default_factory=dict)
    missing_breakdown_by_id: dict[str, list[MissingIngredientBreakdown]] = field(default_factory=dict)
    progress_events: list[str] = field(default_factory=list)
    last_observation: object | None = None

    def record_progress(self, event: str) -> None:
        self.progress_events.append(event)

    def remaining_candidate_capacity(self) -> int:
        return max(0, MAX_EVALUATED_CANDIDATES - len(self.evaluated_candidates))

    def attempts_exhausted(self) -> bool:
        return self.search_attempts >= self.max_search_attempts

    def candidate_cap_reached(self) -> bool:
        return len(self.evaluated_candidates) >= MAX_EVALUATED_CANDIDATES

    def has_prior_attempt(self) -> bool:
        return bool(self.searched_strategies)

    def last_attempt(self) -> SearchAttemptRecord | None:
        return self.searched_strategies[-1] if self.searched_strategies else None
