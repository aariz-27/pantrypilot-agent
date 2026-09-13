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
from app.agent.ingredient_resolution import PantryTermResolution
from app.domain.serving_scaler import ScaledRecipe
from app.recipe.provider import SearchStrategy

MAX_SEARCH_ATTEMPTS = 3
MAX_EVALUATED_CANDIDATES = 20
# Recommendations/additional_options split point only (ticket, 2026-09-13
# recommendation-depth revision): how many of the ranked anchor-feasible
# pool become "recommendations" vs. "additional_options" in
# AgentOrchestrator._finalize. Deliberately left at 3, unchanged --
# raising this to 6 would collapse the recommendations/additional_options
# distinction the frontend's "Show more options" reveal already relies
# on (Option B chosen over Option A: least conceptual debt, zero schema
# change, the frontend already combines both buckets up to
# target_feasible_results for its initial 6-visible display). See
# AgentState.target_feasible_results below for the SEPARATE, now-
# configurable "how many should the agent try to find" stop-policy
# target -- that is the value actually raised to 6.
MAX_FINAL_RECOMMENDATIONS = 3
DEFAULT_TARGET_FEASIBLE_RESULTS = 6
MAX_CORRECTIVE_RETRIES_PER_STEP = 1
# PR #15 HTTP-500 fix (2026-09-09): a structurally-valid action Python
# rejects (AgentUnsupportedActionError -- e.g. a search anchor not
# grounded in the user's pantry) never reaches _run_attempt, so it never
# consumes a search attempt (MAX_SEARCH_ATTEMPTS) or an evaluated
# candidate (MAX_EVALUATED_CANDIDATES). Without an independent bound the
# agent could repeat invalid actions indefinitely. Distinct from
# MAX_CORRECTIVE_RETRIES_PER_STEP, which only bounds a single decision
# step's malformed/schema-invalid output -- this bounds the number of
# structurally-valid-but-policy-rejected actions tolerated across the
# WHOLE run before AgentOrchestrator.run gives up and finalizes
# gracefully from whatever valid candidates already exist, rather than
# ever propagating the rejection as an unhandled exception.
MAX_UNSUPPORTED_ACTION_CORRECTIONS = 2


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
    # 2026-09-13 unified ingredient resolution ticket: pantry text that
    # failed LOCAL canonical/alias resolution but WAS safely grounded
    # against RecipeAPI.io's own ingredient catalogue (or an LLM
    # proposal re-grounded the same way) -- keyed by the cleaned raw
    # text identity (app.domain.ingredient_normalizer.normalize_raw_text_identity),
    # valued by the exact provider-facing search term to use for it.
    # These entries are NEVER canonical ids and NEVER feed pantry
    # coverage/matching/pricing (see app.agent.ingredient_resolution's
    # module docstring) -- they exist ONLY to let
    # _require_anchors_grounded_in_pantry accept an anchor PantryPilot's
    # local taxonomy has never learned, e.g. "chicken" (a real RecipeAPI.io
    # ingredient with no generic PantryPilot canonical id at all).
    pantry_free_text: dict[str, str] = field(default_factory=dict)
    # Cleaned raw pantry text -> canonical id, for entries that only
    # resolved to a real canonical id via LLM typo-correction (never
    # via plain local normalization -- those are already reachable
    # through pantry_canonical directly). Lets an LLM anchor choice
    # that repeats the user's ORIGINAL (possibly misspelled) pantry
    # text -- e.g. "chiken brest" -- still be recognized as the same,
    # now-resolved pantry item in _require_anchors_grounded_in_pantry.
    pantry_raw_to_canonical: dict[str, str] = field(default_factory=dict)
    # Identity (canonical_id OR a pantry_free_text key) -> the exact
    # RecipeAPI.io search term to use for it, resolved lazily (only for
    # identities actually chosen as a search anchor -- ticket section
    # 25) and memoized here for the rest of this run (pagination/retry
    # reuse the same anchor without a repeat catalogue lookup) as well
    # as cross-request via app.integrations.provider_ingredient_cache.
    # Pre-seeded with pantry_free_text's own entries, since those are
    # already fully resolved by the time AgentState is constructed.
    pantry_provider_terms: dict[str, str] = field(default_factory=dict)
    # Full per-pantry-item resolution diagnostics (ticket section 26) --
    # never exposed to end users, but lets tests/logs assert exactly
    # how each raw pantry phrase was resolved (LOCAL_EXACT,
    # PROVIDER_CATALOG_RESOLVED, LLM_CORRECTED_AND_GROUNDED, UNRESOLVED,
    # AMBIGUOUS, ...). Populated once, in AgentOrchestrator._init_state.
    pantry_resolution_log: tuple[PantryTermResolution, ...] = field(default_factory=tuple)

    search_attempts: int = 0
    max_search_attempts: int = MAX_SEARCH_ATTEMPTS
    # Per-run override of how many strong same-anchor feasible
    # candidates the stop-policy signal (sufficient_feasible_found)
    # treats as "enough" -- same per-instance-overridable-default
    # pattern as max_search_attempts above. Set from
    # Settings.target_feasible_results by AgentOrchestrator so it can
    # be tuned per deployment (trial vs. post-trial quota) without a
    # code change.
    target_feasible_results: int = DEFAULT_TARGET_FEASIBLE_RESULTS
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
    # Priority 5 (PR #15 correction pass, 2026-09-08): the canonical id
    # of the FIRST anchor ingredient in the most recent SEARCH action --
    # i.e. exactly the same "primary anchor" convention already used by
    # RecipeAPIIOAdapter.enrich_with_free_text_search, just carried
    # forward into the observation loop so anchor relevance is visible
    # to the agent. Never independently chosen/classified by Python --
    # this only ever mirrors the LLM's own most recent anchor choice
    # (DEC-005: the LLM owns search strategy, including which pantry
    # ingredient is the strongest anchor). None until the first search.
    active_anchor_canonical: str | None = None
    # PR #15 fourth correction pass (2026-09-08, Blocker 4): whether a
    # reviewed broader provider-search term has already been tried FOR
    # THE CURRENT active_anchor_canonical -- resets to False whenever
    # the anchor itself changes (a fresh anchor has never had broadening
    # tried for it yet). Lets the observation loop tell the agent "you
    # already tried the broader term" instead of only "a broader term
    # exists", so it does not repeat the exact same broadening attempt.
    active_anchor_broadening_used: bool = False
    # PR #15 HTTP-500 fix (2026-09-09): count of AgentUnsupportedActionError
    # rejections recovered from so far this run (see AgentOrchestrator.run
    # and MAX_UNSUPPORTED_ACTION_CORRECTIONS above). Monotonic, never
    # decremented -- a bounded corrective-action budget, independent of
    # search_attempts/evaluated_candidates.
    unsupported_action_corrections: int = 0

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
