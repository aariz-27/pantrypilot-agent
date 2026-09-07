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
from app.agent.observations import ObservationCandidate, SearchObservation, build_decision_payload
from app.agent.policy import SYSTEM_POLICY
from app.agent.state import MAX_CORRECTIVE_RETRIES_PER_STEP, MAX_FINAL_RECOMMENDATIONS, AgentState, SearchAttemptRecord
from app.agent.tools import (
    TRANSIENT_ERROR_CATEGORIES,
    evaluate_and_rank,
    execute_search,
    fetch_recipe_details,
    is_approved_local_curated_intent,
)
from app.domain.grocery_taxonomy import CANONICAL_GROCERY_INGREDIENTS, GROCERY_INGREDIENT_ALIASES
from app.domain.ingredient_normalizer import normalize_ingredient_name, normalize_pantry
from app.domain.models import CandidateEvaluation, UserConstraints
from app.domain.ranker import rank_candidates
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

        while True:
            if state.attempts_exhausted():
                state.record_progress("stop: search attempt limit reached")
                return self._finalize(state, "attempt_limit_reached")
            if state.candidate_cap_reached():
                state.record_progress("stop: evaluated-candidate cap reached")
                return self._finalize(state, "candidate_cap_reached")

            action = await self._decide_next_action(state)

            if action.action_type == ActionType.STOP:
                state.record_progress(f"stop: {action.stop.reason.value}")
                return self._finalize(state, action.stop.reason.value)

            if action.action_type == ActionType.SEARCH:
                await self._handle_search(state, action.search, constraints)
            elif action.action_type == ActionType.PAGINATE:
                self._require_paginatable(state)
                await self._run_attempt(state, state.last_attempt().route, self._next_page_strategy(state), constraints)
            elif action.action_type == ActionType.RETRY:
                self._require_retryable(state)
                last = state.last_attempt()
                await self._run_attempt(state, last.route, last.strategy, constraints)

    # -- setup -----------------------------------------------------------

    def _init_state(self, request: AgentRequest) -> AgentState:
        pantry = normalize_pantry(request.pantry_raw, CANONICAL_GROCERY_INGREDIENTS, GROCERY_INGREDIENT_ALIASES)
        excluded = normalize_pantry(request.excluded_raw, CANONICAL_GROCERY_INGREDIENTS, GROCERY_INGREDIENT_ALIASES)
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
        )

    def _constraints(self, request: AgentRequest, excluded_canonical: frozenset[str]) -> UserConstraints:
        return UserConstraints(
            budget_aed=request.budget_aed,
            excluded_canonical=excluded_canonical,
            cuisine_preference=request.cuisine_preference,
            cuisine_strict=request.cuisine_strict,
            max_total_time_minutes=request.max_total_time_minutes,
        )

    # -- decision step (LLM boundary) -------------------------------------

    async def _decide_next_action(self, state: AgentState) -> AgentAction:
        request = LLMDecisionRequest(
            system_policy=SYSTEM_POLICY,
            action_schema=_ACTION_SCHEMA,
            observation=build_decision_payload(state),
        )
        error_message: str | None = None

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

    def _require_anchors_grounded_in_pantry(self, state: AgentState, anchor_ingredients: list[str]) -> None:
        """Deterministic enforcement (independent review finding,
        2026-09-07): SYSTEM_POLICY instructs a real model to choose
        anchors from the user's actual pantry, but a system-prompt
        instruction is not itself a control -- the LLM is never trusted
        to honor it. Every anchor is normalized exactly as pantry_raw
        was in _init_state and must resolve to a canonical ID the user
        actually has; an anchor that fails to resolve, or resolves to an
        ingredient outside pantry_canonical, is rejected outright, never
        silently dropped or substituted for a different one."""

        for anchor in anchor_ingredients:
            result = normalize_ingredient_name(anchor, CANONICAL_GROCERY_INGREDIENTS, GROCERY_INGREDIENT_ALIASES)
            if result.canonical_id is None or result.canonical_id not in state.pantry_canonical:
                raise AgentUnsupportedActionError(
                    f"search anchor {anchor!r} is not present in the user's pantry; anchors must be "
                    "grounded in the user's actual canonical pantry, never invented"
                )

    async def _handle_search(self, state: AgentState, args: SearchArgs, constraints: UserConstraints) -> None:
        self._require_anchors_grounded_in_pantry(state, args.anchor_ingredients)

        route = args.route.value
        if route == "local_curated" and not is_approved_local_curated_intent(args.cuisine, state.cuisine_preference):
            raise AgentUnsupportedActionError(
                "local_curated route requested outside its approved Indian/Pakistani/desi regional scope"
            )

        strategy = SearchStrategy(query_ingredients=args.anchor_ingredients, cuisine=args.cuisine, page=1)
        signature = (route, tuple(sorted(i.lower() for i in args.anchor_ingredients)), (args.cuisine or "").lower())
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

        recipes, _failed_ids = await fetch_recipe_details(provider, to_fetch)
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

        state.record_progress(
            f"attempt {state.search_attempts}: route={route} new_items={len(new_items)} feasible={len(feasible)}"
        )
        state.last_observation = self._build_observation(state, route, strategy, outcome, recipes, feasible, rejected)

    def _merge_best_feasible(
        self, state: AgentState, new_feasible: list[CandidateEvaluation], constraints: UserConstraints
    ) -> list[CandidateEvaluation]:
        combined: dict[str, CandidateEvaluation] = {c.recipe_id: c for c in state.best_feasible}
        for c in new_feasible:
            combined[c.recipe_id] = c
        if not combined:
            return []
        cuisine_by_id = {rid: meta[0] for rid, meta in state.recipe_meta_by_id.items()}
        name_by_id = {rid: meta[1] for rid, meta in state.recipe_meta_by_id.items()}
        ranked = rank_candidates(list(combined.values()), constraints, cuisine_by_id, name_by_id)
        return ranked[:MAX_FINAL_RECOMMENDATIONS]

    def _build_observation(
        self, state, route, strategy, outcome, recipes, feasible, rejected
    ) -> SearchObservation:
        from app.domain.models import RejectionReason

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
        poor_pantry_overlap = bool(evaluated_this_attempt) and (
            sum(e.pantry_coverage for e in evaluated_this_attempt) / len(evaluated_this_attempt) < (1 / 3)
        )

        name_by_id = {r.id: r.name for r in recipes}
        provider_by_id = {r.id: r.provider for r in recipes}
        top = tuple(
            ObservationCandidate(
                recipe_id=c.recipe_id,
                provider=provider_by_id.get(c.recipe_id, c.provider),
                name=name_by_id.get(c.recipe_id, ""),
                cuisine_match=c.cuisine_match,
                hard_constraint_pass=c.hard_constraint_pass,
                rejection_reasons=tuple(r.value for r in c.rejection_reasons),
            )
            for c in evaluated_this_attempt[:5]
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
            poor_pantry_overlap=poor_pantry_overlap,
            has_more_pages=outcome.has_more,
            total_feasible_so_far=len(state.best_feasible),
            total_evaluated_so_far=len(state.evaluated_candidates),
            candidate_cap_remaining=state.remaining_candidate_capacity(),
            search_attempts_remaining=max(0, state.max_search_attempts - state.search_attempts),
            top_candidates=top,
        )

    # -- finalization ------------------------------------------------------

    def _closest_alternatives(self, state: AgentState) -> list[CandidateEvaluation]:
        rejected = [c for c in state.evaluated_candidates if not c.hard_constraint_pass]
        rejected.sort(key=lambda c: (len(c.rejection_reasons), -c.pantry_coverage))
        return rejected[:MAX_FINAL_RECOMMENDATIONS]

    def _finalize(self, state: AgentState, stop_reason: str) -> AgentResult:
        status = "completed" if state.best_feasible else "no_feasible_match"
        return AgentResult(
            request_id=state.request_id,
            status=status,
            search_attempts=state.search_attempts,
            recommendations=list(state.best_feasible[:MAX_FINAL_RECOMMENDATIONS]),
            closest_alternatives=[] if state.best_feasible else self._closest_alternatives(state),
            stop_reason=stop_reason,
            progress_events=list(state.progress_events),
            provider_status=dict(state.provider_status),
        )
