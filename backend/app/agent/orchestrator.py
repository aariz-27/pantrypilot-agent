"""M03 Agent Orchestrator (TECHNICAL_SPEC.md sections 3-4).

Owns goal/state, tool selection, retry/replan and stop behavior. Never
calculates prices/scores and never parses provider payloads itself --
those remain app.agent.tools' (composing Modules A-C) and the
integrations layer's jobs respectively. The LLM is asked, at each
decision step, to choose one bounded typed action
(app.agent.actions.AgentAction); Python independently enforces every
hard bound in TECHNICAL_SPEC.md section 2 regardless of what the LLM
requests.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import ValidationError

from app.agent.actions import ActionType, AgentAction, SearchArgs
from app.agent.errors import AgentMalformedActionError, AgentUnsupportedActionError
from app.agent.observations import (
    ObservationCandidate,
    SearchObservation,
    build_decision_payload,
    candidate_contains_anchor,
    compute_anchor_stats,
)
from app.agent.policy import SYSTEM_POLICY
from app.agent.state import (
    MAX_CORRECTIVE_RETRIES_PER_STEP,
    MAX_FINAL_RECOMMENDATIONS,
    MAX_UNSUPPORTED_ACTION_CORRECTIONS,
    AgentState,
    SearchAttemptRecord,
)
from app.agent.tools import (
    TRANSIENT_ERROR_CATEGORIES,
    evaluate_and_rank,
    execute_search,
    fetch_recipe_details,
    is_approved_local_curated_intent,
    normalize_recipe_ingredients,
)
from app.domain.cost_engine import MissingIngredientBreakdown, estimate_missing_ingredient_breakdown
from app.domain.grocery_taxonomy import CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES
from app.domain.ingredient_normalizer import normalize_ingredient_name, normalize_pantry
from app.domain.models import CandidateEvaluation, Recipe, RejectionReason, UserConstraints
from app.domain.ranker import rank_candidates
from app.domain.serving_scaler import ScaledRecipe, scale_recipe_servings
from app.integrations.llm_provider import LLMDecisionRequest, LLMProvider, LLMProviderMalformedResponseError
from app.recipe.provider import RecipeProvider, SearchStrategy
from app.repositories.price_repository import PriceRepository

_ACTION_SCHEMA = AgentAction.model_json_schema()


@dataclass(frozen=True)
class AgentRequest:
    request_id: str
    pantry_raw: list[str]
    budget_aed: float | None
    cuisine_preference: str | None
    cuisine_strict: bool
    servings: int
    max_total_time_minutes: int | None
    excluded_raw: list[str] = field(default_factory=list)
    allow_hard_difficulty: bool = False


@dataclass(frozen=True)
class AgentResult:
    request_id: str
    status: str  # "completed" | "no_feasible_match"
    search_attempts: int
    recommendations: list[CandidateEvaluation]
    closest_alternatives: list[CandidateEvaluation]
    stop_reason: str | None
    progress_events: list[str]
    provider_status: dict[str, str]
    # Module E: user-facing detail for every recipe_id appearing in
    # recommendations/closest_alternatives, for the API layer to build
    # cards/detail views from without re-deriving anything itself.
    recipe_by_id: dict[str, Recipe]
    scaling_by_id: dict[str, ScaledRecipe]
    missing_breakdown_by_id: dict[str, list[MissingIngredientBreakdown]]
    pantry_unresolved: list[str]
    # Module E post-review addition (2026-09-08, PR #15): deterministic
    # summary only -- never chain-of-thought/raw actions/prompts -- so
    # the UI can tell the user when a genuinely better pantry match was
    # excluded purely for exceeding max_total_time_minutes, without
    # silently hiding that trade-off or ever relaxing the constraint
    # itself.
    higher_match_time_excluded: bool = False
    higher_match_time_excluded_count: int = 0
    higher_match_min_rejected_time_minutes: int | None = None
    # Priority 4 (PR #15 correction pass, 2026-09-08): already-evaluated,
    # already-hard-constraint-passing candidates ranked 4th or lower --
    # never a "final recommendation" (max 3 remains unchanged), never a
    # hard-rejected candidate (that is closest_alternatives' job). Lets
    # the UI reveal more good options with zero additional provider/LLM
    # calls, since these were already fully retrieved and evaluated
    # during the normal bounded search. Defaulted (unlike recommendations/
    # closest_alternatives) purely so existing keyword-constructed test
    # fixtures that don't care about it don't all need updating --
    # _finalize (the only production constructor) always sets it
    # explicitly.
    additional_options: list[CandidateEvaluation] = field(default_factory=list)
    # PR #15 second correction pass (2026-09-08): whether each candidate
    # in recommendations/additional_options contains the run's active
    # anchor (see AgentState.active_anchor_canonical / observations.
    # candidate_contains_anchor). Lets the API/UI layer clearly label a
    # reserve candidate that only appears because the anchor-matching
    # pool was exhausted, rather than presenting it as an equally strong
    # match. Empty when no anchor was ever defined for this run.
    anchor_match_by_id: dict[str, bool] = field(default_factory=dict)


class AgentOrchestrator:
    def __init__(
        self,
        llm_provider: LLMProvider,
        recipe_providers: dict[str, RecipeProvider],
        price_repository: PriceRepository,
    ) -> None:
        self._llm = llm_provider
        self._providers = recipe_providers
        self._price_repository = price_repository

    async def run(self, request: AgentRequest) -> AgentResult:
        state = self._init_state(request)
        constraints = self._constraints(request, state.excluded_canonical)

        if request.pantry_raw and not state.pantry_canonical:
            state.record_progress("stop: all pantry ingredients unresolved")
            return self._finalize(state, "input_makes_search_impossible")

        # PR #15 HTTP-500 fix (2026-09-09): unsupported_action_feedback
        # seeds the NEXT decision step with structured, deterministic
        # corrective feedback whenever the immediately preceding action
        # was rejected as AgentUnsupportedActionError below -- never a
        # bare unhandled exception reaching the API layer. None on every
        # other iteration.
        unsupported_action_feedback: str | None = None
        while True:
            if state.attempts_exhausted():
                state.record_progress("stop: search attempt limit reached")
                return self._finalize(state, "attempt_limit_reached")
            if state.candidate_cap_reached():
                state.record_progress("stop: evaluated-candidate cap reached")
                return self._finalize(state, "candidate_cap_reached")

            action = await self._decide_next_action(state, unsupported_action_feedback)
            unsupported_action_feedback = None

            if action.action_type == ActionType.STOP:
                state.record_progress(f"stop: {action.stop.reason.value}")
                return self._finalize(state, action.stop.reason.value)

            try:
                if action.action_type == ActionType.SEARCH:
                    await self._handle_search(state, action.search, constraints)
                elif action.action_type == ActionType.PAGINATE:
                    self._require_paginatable(state)
                    await self._run_attempt(
                        state, state.last_attempt().route, self._next_page_strategy(state), constraints
                    )
                elif action.action_type == ActionType.RETRY:
                    self._require_retryable(state)
                    last = state.last_attempt()
                    await self._run_attempt(state, last.route, last.strategy, constraints)
            except AgentUnsupportedActionError as exc:
                # The action was schema-valid (already past
                # AgentAction.model_validate) but violates a bounded
                # orchestration policy the schema alone cannot express --
                # e.g. a search anchor not grounded in the user's actual
                # pantry (never weakened here; _require_anchors_grounded_
                # in_pantry is untouched and still rejects it exactly as
                # before). This is an EXPECTED, bounded agent-action
                # failure, not a fatal internal error -- it must recover,
                # never propagate to the global HTTP handler as a 500.
                state.unsupported_action_corrections += 1
                state.record_progress(f"corrective: unsupported action rejected -- {exc.message}")
                if state.unsupported_action_corrections > MAX_UNSUPPORTED_ACTION_CORRECTIONS:
                    # Correction budget exhausted (or Claude keeps
                    # repeating an invalid action) -- stop bounded
                    # orchestration gracefully and finalize from whatever
                    # valid candidates already exist, per the ticket's
                    # required graceful-stop behavior.
                    state.record_progress("stop: unsupported-action correction budget exhausted")
                    return self._finalize(state, "unsupported_action_budget_exhausted")
                unsupported_action_feedback = self._unsupported_action_feedback(state, exc)

    # -- setup -----------------------------------------------------------

    def _init_state(self, request: AgentRequest) -> AgentState:
        pantry = normalize_pantry(request.pantry_raw, CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES)
        excluded = normalize_pantry(request.excluded_raw, CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES)
        return AgentState(
            request_id=request.request_id,
            pantry_raw=list(request.pantry_raw),
            pantry_canonical=pantry.canonical_ids,
            budget_aed=request.budget_aed,
            cuisine_preference=request.cuisine_preference,
            cuisine_strict=request.cuisine_strict,
            servings=request.servings,
            max_total_time_minutes=request.max_total_time_minutes,
            excluded_raw=list(request.excluded_raw),
            excluded_canonical=excluded.canonical_ids,
            pantry_unresolved=pantry.unresolved,
        )

    def _constraints(self, request: AgentRequest, excluded_canonical: frozenset[str]) -> UserConstraints:
        return UserConstraints(
            budget_aed=request.budget_aed,
            excluded_canonical=excluded_canonical,
            cuisine_preference=request.cuisine_preference,
            cuisine_strict=request.cuisine_strict,
            max_total_time_minutes=request.max_total_time_minutes,
            allow_hard_difficulty=request.allow_hard_difficulty,
        )

    # -- decision step (LLM boundary) -------------------------------------

    async def _decide_next_action(
        self, state: AgentState, unsupported_action_feedback: str | None = None
    ) -> AgentAction:
        request = LLMDecisionRequest(
            system_policy=SYSTEM_POLICY,
            action_schema=_ACTION_SCHEMA,
            observation=build_decision_payload(state),
        )
        # Seeds the corrective feedback from a PRIOR step's rejected
        # AgentUnsupportedActionError (ticket: HTTP-500 fix), if any --
        # so the very first request of this decision step already tells
        # Claude why its last action was rejected and what is actually
        # allowed. Independent of, and composes with, the malformed-
        # schema corrective retry loop below: if this same corrective
        # response is itself malformed, that is still bounded by
        # MAX_CORRECTIVE_RETRIES_PER_STEP as before.
        error_message: str | None = unsupported_action_feedback

        for attempt in range(MAX_CORRECTIVE_RETRIES_PER_STEP + 1):
            step_request = request if error_message is None else LLMDecisionRequest(
                system_policy=request.system_policy,
                action_schema=request.action_schema,
                observation=request.observation,
                previous_action_error=error_message,
            )
            try:
                response = await self._llm.decide(step_request)
                return AgentAction.model_validate(response.raw_action)
            except (ValidationError, LLMProviderMalformedResponseError) as exc:
                # Both a schema-invalid action and a response with no
                # usable tool call at all are "malformed LLM output"
                # under the same one-corrective-retry policy (ticket
                # section 14). Other LLMProviderError categories
                # (timeout/unavailable/configuration) are a different
                # failure class -- a genuine service failure, not
                # malformed output -- and are deliberately not caught
                # here; they propagate as-is rather than being retried.
                error_message = f"previous action was rejected: {type(exc).__name__}"
                if attempt >= MAX_CORRECTIVE_RETRIES_PER_STEP:
                    raise AgentMalformedActionError(
                        "LLM action output remained invalid after one corrective retry"
                    ) from None

        raise AgentMalformedActionError("LLM action output remained invalid after one corrective retry")

    # -- action handlers ---------------------------------------------------

    def _require_paginatable(self, state: AgentState) -> None:
        last = state.last_attempt()
        if last is None or last.outcome != "ok" or not last.has_more:
            raise AgentUnsupportedActionError(
                "paginate requested with no prior successful, has_more search attempt to continue"
            )

    def _require_retryable(self, state: AgentState) -> None:
        last = state.last_attempt()
        if last is None or last.outcome not in TRANSIENT_ERROR_CATEGORIES:
            raise AgentUnsupportedActionError(
                "retry requested but the immediately preceding attempt was not a transient provider failure"
            )

    def _next_page_strategy(self, state: AgentState) -> SearchStrategy:
        last = state.last_attempt()
        return last.strategy.model_copy(update={"page": last.strategy.page + 1})

    def _require_anchors_grounded_in_pantry(self, state: AgentState, anchor_ingredients: list[str]) -> list[str]:
        """Deterministic enforcement (independent review finding,
        2026-09-07): SYSTEM_POLICY instructs a real model to choose
        anchors from the user's actual pantry, but a system-prompt
        instruction is not itself a control -- the LLM is never trusted
        to honor it. Every anchor is normalized exactly as pantry_raw
        was in _init_state and must resolve to a canonical ID the user
        actually has; an anchor that fails to resolve, or resolves to an
        ingredient outside pantry_canonical, is rejected outright, never
        silently dropped or substituted for a different one.

        Returns the resolved canonical ids, in the same order (PR #15
        fourth correction pass, 2026-09-08, Blocker 2): the caller uses
        these -- not the LLM's raw anchor text -- to build the provider
        query, so canonical identity and provider-search wording stay
        cleanly separated regardless of whether the LLM sent the exact
        canonical id or an alias that resolves to it."""

        canonical_ids: list[str] = []
        for anchor in anchor_ingredients:
            result = normalize_ingredient_name(anchor, CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES)
            if result.canonical_id is None or result.canonical_id not in state.pantry_canonical:
                raise AgentUnsupportedActionError(
                    f"search anchor {anchor!r} is not present in the user's pantry; anchors must be "
                    "grounded in the user's actual canonical pantry, never invented"
                )
            canonical_ids.append(result.canonical_id)
        return canonical_ids

    def _unsupported_action_feedback(self, state: AgentState, exc: AgentUnsupportedActionError) -> str:
        """Structured, deterministic corrective observation for a
        rejected-but-structurally-valid action (ticket: HTTP-500 fix).
        `exc.message` is always a pre-written, safe string (every
        PantryPilotError subclass -- see app.domain.errors) that already
        names the concrete proposed value and why it was rejected (e.g.
        the invalid anchor and "not present in the user's pantry" for
        the grounding guard). This always additionally names the full
        set of grounded pantry canonical ids Claude may actually choose
        from, so the next decision has everything it needs to
        self-correct without ever inventing or broadening beyond the
        user's real pantry -- this is feedback DATA, never an
        instruction the model is trusted to enforce on its own; the
        underlying guards remain the sole control."""

        return (
            f"{exc.message} Allowed pantry canonical anchors: {sorted(state.pantry_canonical)}. "
            "Choose a new search using only these grounded anchors, or a valid "
            "paginate/retry action for the immediately preceding attempt, or stop."
        )

    async def _handle_search(self, state: AgentState, args: SearchArgs, constraints: UserConstraints) -> None:
        anchor_canonical_ids = self._require_anchors_grounded_in_pantry(state, args.anchor_ingredients)

        # Priority 5 (PR #15 correction pass, 2026-09-08): carry the
        # LLM's own primary-anchor choice into the observation loop.
        # Already validated above to resolve to a real pantry canonical
        # id. Same "first anchor is the primary one" convention
        # RecipeAPIIOAdapter.enrich_with_free_text_search already uses,
        # not a new one.
        new_anchor = anchor_canonical_ids[0]
        if new_anchor != state.active_anchor_canonical:
            # PR #15 fourth correction pass (2026-09-08, Blocker 4): a
            # fresh anchor has never had broadening tried for it yet --
            # reset so the observation doesn't wrongly claim otherwise.
            state.active_anchor_broadening_used = False
        state.active_anchor_canonical = new_anchor
        if args.broaden_provider_search:
            state.active_anchor_broadening_used = True

        route = args.route.value
        if route == "local_curated" and not is_approved_local_curated_intent(args.cuisine, state.cuisine_preference):
            raise AgentUnsupportedActionError(
                "local_curated route requested outside its approved Indian/Pakistani/desi regional scope"
            )

        strategy = SearchStrategy(
            # PR #15 fourth correction pass (2026-09-08, Blocker 2): the
            # RESOLVED canonical ids, not the LLM's raw anchor text --
            # keeps canonical identity and provider-search wording
            # cleanly separated regardless of whether the LLM sent an
            # exact canonical id or an alias that resolves to one. Any
            # broadening happens only inside the adapter, keyed off
            # these exact ids (RecipeAPIIOAdapter.
            # PROVIDER_SEARCH_TERM_OVERRIDES).
            query_ingredients=anchor_canonical_ids,
            cuisine=args.cuisine,
            page=1,
            enrich_free_text=args.enrich_free_text,
            broaden_provider_search=args.broaden_provider_search,
        )
        # enrich_free_text/broaden_provider_search are included (PR #15
        # correction passes, 2026-09-08): re-issuing the same anchors
        # with either flag newly requested is a materially different
        # provider request (an extra free-text query merged in, or
        # different query text), not a repeat -- excluding enrich_free_text
        # here previously made that legitimate corrective action bounce
        # as "identical", discovered via a live Test A run; the same
        # reasoning applies to broaden_provider_search.
        signature = (
            route,
            tuple(sorted(anchor_canonical_ids)),
            (args.cuisine or "").lower(),
            args.enrich_free_text,
            args.broaden_provider_search,
        )
        if signature in state.distinct_search_signatures:
            raise AgentUnsupportedActionError(
                "an identical search strategy was already attempted; use retry only after a transient "
                "provider failure, or choose a materially different strategy"
            )
        state.distinct_search_signatures.add(signature)

        await self._run_attempt(state, route, strategy, constraints)

    async def _run_attempt(
        self, state: AgentState, route: str, strategy: SearchStrategy, constraints: UserConstraints
    ) -> None:
        provider = self._providers.get(route)
        outcome = await execute_search(provider, strategy)

        state.search_attempts += 1
        state.searched_strategies.append(
            SearchAttemptRecord(route=route, strategy=strategy, outcome=outcome.error_category or "ok", has_more=outcome.has_more)
        )
        state.provider_status[route] = outcome.error_category or "ok"

        if outcome.error_category is not None:
            state.record_progress(f"attempt {state.search_attempts}: route={route} error={outcome.error_category}")
            state.last_observation = SearchObservation(
                attempt_number=state.search_attempts,
                route=route,
                strategy_summary={"anchor_ingredients": strategy.query_ingredients, "cuisine": strategy.cuisine, "page": strategy.page},
                provider_error_category=outcome.error_category,
                items_returned=0,
                items_new=0,
                items_evaluated_this_attempt=0,
                feasible_count_this_attempt=0,
                all_over_budget=False,
                all_strict_cuisine_mismatch=False,
                poor_pantry_overlap=False,
                has_more_pages=False,
                total_feasible_so_far=len(state.best_feasible),
                total_evaluated_so_far=len(state.evaluated_candidates),
                candidate_cap_remaining=state.remaining_candidate_capacity(),
                search_attempts_remaining=max(0, state.max_search_attempts - state.search_attempts),
            )
            return

        new_items = [
            item for item in outcome.items if (item.provider, item.provider_recipe_id) not in state.candidate_ids_seen
        ]
        state.candidate_ids_seen.update((item.provider, item.provider_recipe_id) for item in outcome.items)
        capacity = state.remaining_candidate_capacity()
        to_fetch = new_items[:capacity]

        fetched_recipes, _failed_ids = await fetch_recipe_details(provider, to_fetch)

        # Module E: deterministic serving scaling, applied once per
        # recipe right after grounding and before any evaluation/costing
        # so the scaled quantities are what the Cost Engine sees.
        # Never done by the LLM (docs/AGENTS.md).
        recipes: list[Recipe] = []
        for raw_recipe in fetched_recipes:
            scaled = scale_recipe_servings(raw_recipe, state.servings)
            state.scaling_by_id[raw_recipe.id] = scaled
            normalized_scaled = normalize_recipe_ingredients(scaled.recipe)
            state.recipe_by_id[raw_recipe.id] = normalized_scaled
            recipes.append(scaled.recipe)

        for recipe in recipes:
            # Keyed by recipe.id (e.g. "recipeapi_io:1"): this string is
            # always built by app.recipe.mapping.build_recipe_id from the
            # SAME (provider, provider_recipe_id) tuple used above, so it
            # carries the tuple identity faithfully without this code
            # re-parsing/re-deriving it independently. It is also the
            # exact key app.domain.ranker.rank_candidates requires for
            # its cuisine_by_id/name_by_id maps (a frozen Module A
            # contract), so this dict is intentionally string-keyed
            # rather than tuple-keyed like candidate_ids_seen above.
            state.recipe_meta_by_id[recipe.id] = (recipe.cuisine, recipe.name)

        feasible, rejected = evaluate_and_rank(recipes, state.pantry_canonical, constraints, self._price_repository)
        state.evaluated_candidates.extend(feasible + rejected)
        state.best_feasible = self._merge_best_feasible(state, feasible, constraints)

        # Module E: ingredient-level cost breakdown for every evaluated
        # candidate (feasible or not -- closest alternatives need it
        # too), derived from the same normalized+scaled recipe already
        # cached above. Deterministic re-derivation only -- no LLM, no
        # new pricing rule, reuses estimate_missing_ingredient_breakdown.
        for candidate in feasible + rejected:
            normalized_recipe = state.recipe_by_id.get(candidate.recipe_id)
            if normalized_recipe is None:
                continue
            missing_ids = set(candidate.missing_ingredients)
            missing_lines = [ing for ing in normalized_recipe.ingredients if ing.canonical_id in missing_ids]
            state.missing_breakdown_by_id[candidate.recipe_id] = estimate_missing_ingredient_breakdown(
                missing_lines, self._price_repository
            )

        state.record_progress(
            f"attempt {state.search_attempts}: route={route} new_items={len(new_items)} feasible={len(feasible)}"
        )
        state.last_observation = self._build_observation(state, route, strategy, outcome, recipes, feasible, rejected)

    def _merge_best_feasible(
        self, state: AgentState, new_feasible: list[CandidateEvaluation], constraints: UserConstraints
    ) -> list[CandidateEvaluation]:
        """Priority-4 change (PR #15 correction pass, 2026-09-08): returns
        the FULL ranked feasible pool (bounded only by
        MAX_EVALUATED_CANDIDATES=20, same as state.evaluated_candidates),
        not just the top 3. Previously this truncated to
        MAX_FINAL_RECOMMENDATIONS here, silently discarding already-
        evaluated, already-feasible candidates ranked 4th or lower --
        exactly the "additional_options" reserve candidates Priority 4
        needs to expose without any new provider/LLM call. Truncation to
        the top-3 "final recommendations" now happens only once, in
        _finalize, which is also where the max-3 invariant is enforced
        for the public AgentResult.recommendations contract -- this
        method's own return value was never itself the invariant."""

        combined: dict[str, CandidateEvaluation] = {c.recipe_id: c for c in state.best_feasible}
        for c in new_feasible:
            combined[c.recipe_id] = c
        if not combined:
            return []
        cuisine_by_id = {rid: meta[0] for rid, meta in state.recipe_meta_by_id.items()}
        name_by_id = {rid: meta[1] for rid, meta in state.recipe_meta_by_id.items()}
        return rank_candidates(list(combined.values()), constraints, cuisine_by_id, name_by_id)

    def _build_observation(
        self, state, route, strategy, outcome, recipes, feasible, rejected
    ) -> SearchObservation:

        evaluated_this_attempt = feasible + rejected
        # Documented implementation thresholds (spec gives no exact
        # number for these aggregate flags -- chosen conservatively,
        # narrow and numeric only, akin to app.domain.ranker's own
        # documented conservative defaults):
        all_over_budget = bool(rejected) and not feasible and all(
            RejectionReason.BUDGET_EXCEEDED in e.rejection_reasons for e in rejected
        )
        all_strict_cuisine_mismatch = bool(rejected) and not feasible and all(
            RejectionReason.STRICT_CUISINE_MISMATCH in e.rejection_reasons for e in rejected
        )
        # Post-review addition (2026-09-08): same pattern as
        # all_over_budget/all_strict_cuisine_mismatch above -- was
        # previously missing for this rejection category despite being
        # just as common a reason a whole attempt yields no feasible
        # candidates (see PR #15 browser-review investigation).
        all_max_total_time_exceeded = bool(rejected) and not feasible and all(
            RejectionReason.MAX_TOTAL_TIME_EXCEEDED in e.rejection_reasons for e in rejected
        )
        poor_pantry_overlap = bool(evaluated_this_attempt) and (
            sum(e.pantry_coverage for e in evaluated_this_attempt) / len(evaluated_this_attempt) < (1 / 3)
        )

        name_by_id = {r.id: r.name for r in recipes}
        provider_by_id = {r.id: r.provider for r in recipes}
        # Post-review fix (2026-09-08): previously the first 5 candidates
        # in raw evaluation order (a RecipeAPI.io relevance ranking, not
        # a pantry-match ranking) were surfaced to the LLM, which could
        # silently omit the attempt's actual best-matching candidates
        # from its decision context entirely. Sorting by the already-
        # computed, deterministic pantry_coverage (descending) before
        # truncating to 5 ensures the agent's summarized view reflects
        # its strongest real evidence -- this only changes what is
        # shown to the LLM for its next-action decision, never the
        # user-facing ranking/scoring formula (app.domain.ranker is
        # untouched).
        best_evidence_first = sorted(evaluated_this_attempt, key=lambda c: -c.pantry_coverage)

        # Priority 5 (PR #15 correction pass, 2026-09-08): per-attempt
        # anchor-relevance evidence (see AnchorStats' docstring --
        # never Python's own choice of anchor, only how well the LLM's
        # own current choice is represented among what THIS attempt
        # returned).
        anchor_stats = compute_anchor_stats(evaluated_this_attempt, state.recipe_by_id, state.active_anchor_canonical)

        top = tuple(
            ObservationCandidate(
                recipe_id=c.recipe_id,
                provider=provider_by_id.get(c.recipe_id, c.provider),
                name=name_by_id.get(c.recipe_id, ""),
                cuisine_match=c.cuisine_match,
                hard_constraint_pass=c.hard_constraint_pass,
                rejection_reasons=tuple(r.value for r in c.rejection_reasons),
                pantry_coverage=round(c.pantry_coverage, 4),
            )
            for c in best_evidence_first[:5]
        )

        return SearchObservation(
            attempt_number=state.search_attempts,
            route=route,
            strategy_summary={"anchor_ingredients": strategy.query_ingredients, "cuisine": strategy.cuisine, "page": strategy.page},
            provider_error_category=None,
            items_returned=len(outcome.items),
            items_new=len(recipes),
            items_evaluated_this_attempt=len(evaluated_this_attempt),
            feasible_count_this_attempt=len(feasible),
            all_over_budget=all_over_budget,
            all_strict_cuisine_mismatch=all_strict_cuisine_mismatch,
            all_max_total_time_exceeded=all_max_total_time_exceeded,
            poor_pantry_overlap=poor_pantry_overlap,
            has_more_pages=outcome.has_more,
            total_feasible_so_far=len(state.best_feasible),
            total_evaluated_so_far=len(state.evaluated_candidates),
            candidate_cap_remaining=state.remaining_candidate_capacity(),
            search_attempts_remaining=max(0, state.max_search_attempts - state.search_attempts),
            top_candidates=top,
            active_search_anchor=anchor_stats.anchor_canonical_id,
            anchor_candidates_this_attempt=anchor_stats.anchor_candidate_count,
            feasible_anchor_candidates_this_attempt=anchor_stats.feasible_anchor_candidate_count,
            best_coverage_among_anchor_candidates_this_attempt=anchor_stats.best_coverage_among_anchor_candidates,
            best_coverage_among_non_anchor_candidates_this_attempt=anchor_stats.best_coverage_among_non_anchor_candidates,
            mostly_generic_overlap_this_attempt=anchor_stats.mostly_generic_overlap,
        )

    # -- finalization ------------------------------------------------------

    def _closest_alternatives(self, state: AgentState) -> list[CandidateEvaluation]:
        rejected = [c for c in state.evaluated_candidates if not c.hard_constraint_pass]
        rejected.sort(key=lambda c: (len(c.rejection_reasons), -c.pantry_coverage))
        return rejected[:MAX_FINAL_RECOMMENDATIONS]

    def _higher_match_time_excluded(
        self, state: AgentState, shown: list[CandidateEvaluation]
    ) -> tuple[bool, int, int | None]:
        """Deterministic summary only (ticket section 3, PR #15 review):
        never chain-of-thought/raw agent actions/internal prompts --
        just whether a genuinely higher-pantry-match candidate exists
        among ALL evaluated candidates (not only the top-3 shown) that
        was hard-rejected specifically for exceeding
        max_total_time_minutes, plus a safely-grounded count and the
        minimum real total time among them. Never used to relax the
        time constraint itself -- that remains the user's decision via
        a new, explicit search (see app/api/recommend_mapping.py's
        "Show longer recipes" handling)."""

        best_shown_coverage = max((c.pantry_coverage for c in shown), default=0.0)
        qualifying = [
            c
            for c in state.evaluated_candidates
            if not c.hard_constraint_pass
            and RejectionReason.MAX_TOTAL_TIME_EXCEEDED in c.rejection_reasons
            and c.pantry_coverage > best_shown_coverage
        ]
        if not qualifying:
            return False, 0, None

        min_time: int | None = None
        for c in qualifying:
            recipe = state.recipe_by_id.get(c.recipe_id)
            if recipe is None or recipe.prep_time_minutes is None or recipe.cook_time_minutes is None:
                continue
            total_time = recipe.prep_time_minutes + recipe.cook_time_minutes
            if min_time is None or total_time < min_time:
                min_time = total_time

        return True, len(qualifying), min_time

    def _partition_by_anchor(
        self, state: AgentState, candidates: list[CandidateEvaluation]
    ) -> tuple[list[CandidateEvaluation], list[CandidateEvaluation]]:
        """Splits an already-ranked candidate list into (anchor-matching,
        non-anchor), preserving the existing frozen-ranking order within
        each group (never a re-score -- app.domain.ranker is untouched).
        No-op partition (everything treated as "anchor-matching") when no
        anchor was ever defined for this run -- there is nothing to
        discriminate by."""

        if state.active_anchor_canonical is None:
            return list(candidates), []

        anchor_matching: list[CandidateEvaluation] = []
        non_anchor: list[CandidateEvaluation] = []
        for candidate in candidates:
            if candidate_contains_anchor(candidate, state.recipe_by_id, state.active_anchor_canonical):
                anchor_matching.append(candidate)
            else:
                non_anchor.append(candidate)
        return anchor_matching, non_anchor

    def _finalize(self, state: AgentState, stop_reason: str) -> AgentResult:
        status = "completed" if state.best_feasible else "no_feasible_match"
        # PR #15 fifth correction pass (2026-09-08, product decision):
        # recommendations and additional_options are now BOTH built
        # exclusively from the anchor-matching feasible pool -- a
        # non-anchor candidate never pads a recommendations slot
        # anymore. "Fewer genuinely relevant recommendations" is now
        # explicitly preferred over "3 padded with an unrelated
        # alternative" (a prior-pass behavior this ticket reverses).
        # Non-anchor FEASIBLE candidates (previously eligible to fill a
        # recommendations slot) now route to closest_alternatives
        # instead -- a structurally and visually separate section,
        # bounded the same way the existing hard-rejected-candidate
        # closest_alternatives path already is. state.best_feasible is
        # still the FULL ranked feasible pool (see _merge_best_feasible)
        # produced by the frozen, unmodified ranker; only how it gets
        # split across the three public buckets changed here.
        anchor_feasible, non_anchor_feasible = self._partition_by_anchor(state, state.best_feasible)
        recommendations = list(anchor_feasible[:MAX_FINAL_RECOMMENDATIONS])
        additional_options = list(anchor_feasible[MAX_FINAL_RECOMMENDATIONS:])
        anchor_match_by_id = (
            {c.recipe_id: True for c in anchor_feasible} | {c.recipe_id: False for c in non_anchor_feasible}
            if state.active_anchor_canonical is not None
            else {}
        )
        if state.best_feasible:
            # Some feasible candidates exist (anchor-matching, non-
            # anchor, or both). Hard-rejected candidates are never
            # relevant here -- only surfaced via _closest_alternatives
            # in the "nothing feasible at all" branch below.
            closest_alternatives = list(non_anchor_feasible[:MAX_FINAL_RECOMMENDATIONS])
        else:
            closest_alternatives = self._closest_alternatives(state)
        higher_match_time_excluded, higher_match_count, higher_match_min_time = self._higher_match_time_excluded(
            state, recommendations or closest_alternatives
        )

        relevant_ids = {c.recipe_id for c in recommendations + additional_options + closest_alternatives}
        return AgentResult(
            request_id=state.request_id,
            status=status,
            search_attempts=state.search_attempts,
            recommendations=recommendations,
            additional_options=additional_options,
            closest_alternatives=closest_alternatives,
            stop_reason=stop_reason,
            progress_events=list(state.progress_events),
            provider_status=dict(state.provider_status),
            recipe_by_id={rid: r for rid, r in state.recipe_by_id.items() if rid in relevant_ids},
            scaling_by_id={rid: s for rid, s in state.scaling_by_id.items() if rid in relevant_ids},
            missing_breakdown_by_id={
                rid: b for rid, b in state.missing_breakdown_by_id.items() if rid in relevant_ids
            },
            pantry_unresolved=list(state.pantry_unresolved),
            higher_match_time_excluded=higher_match_time_excluded,
            higher_match_time_excluded_count=higher_match_count,
            higher_match_min_rejected_time_minutes=higher_match_min_time,
            anchor_match_by_id=anchor_match_by_id,
        )
