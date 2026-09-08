"""Structured, untrusted-data-isolated observations sent to the LLM.

Per ticket section 10, the agent receives STRUCTURED OBSERVATIONS from
the deterministic evaluation pipeline -- never raw recipe instructions,
never internal state beyond what a decision needs. Per ticket section
15, any provider/recipe-derived text (currently just candidate names,
used only so progress observations are legible) is confined to a
clearly-labeled field inside the observation data block built here; it
never reaches app.agent.policy.SYSTEM_POLICY, which is a fixed constant
independent of every field defined in this module.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.agent.state import MAX_FINAL_RECOMMENDATIONS, AgentState
from app.domain.models import CandidateEvaluation, Recipe
from app.recipe.provider import PROVIDER_SEARCH_TERM_OVERRIDES

# Bound the number of individual candidates surfaced to the model --
# the agent needs aggregate signals to decide, not a full listing
# (ticket section 10: "Do not expose unnecessary raw/internal details").
_MAX_OBSERVED_CANDIDATES = 5

# Same conservative threshold AgentOrchestrator._build_observation uses
# for poor_pantry_overlap. Deliberately reused here (Priority-1
# correction, PR #15 correction pass, 2026-09-08): "feasible" only means
# hard_constraint_pass (budget/time/cuisine), which says nothing about
# actual pantry match quality -- a recipe can be fully feasible with
# near-zero pantry overlap. An earlier version of
# sufficient_feasible_found counted feasible candidates alone, which a
# live Test A run showed caused the agent to stop after finding 3+
# feasible-but-irrelevant candidates before ever seeing the genuinely
# relevant ones the free-text enrichment path exists to surface --
# regressing the exact relevance fix Priority-1 item F requires
# preserving. Requiring a minimum average coverage among the best
# feasible candidates closes that gap.
_MIN_AVERAGE_COVERAGE_FOR_SUFFICIENT = 1 / 3

# Priority 5 (PR #15 correction pass, 2026-09-08): a live trace of the
# ticket's own reproduction pantry (Chicken Wings, Garlic, Soy Sauce,
# Ginger, Salt, Pepper) found the agent stopped with 6 feasible
# candidates and a passing average top-3 coverage, yet only 4 of 8
# retained candidates actually contained the chosen anchor
# (chicken_wings) -- the deterministic ranker (frozen, unmodified) then
# legitimately ranked one cheap/few-missing NON-anchor candidate ahead
# of two genuinely relevant anchor candidates. Feasible-count and
# average-coverage alone cannot see this: a pool "diluted" with
# generic-overlap matches (chosen anchor mostly absent) can still clear
# both bars. This conservative majority threshold flags exactly that
# "mostly generic overlap" condition described in the ticket, styled
# the same way as _MIN_AVERAGE_COVERAGE_FOR_SUFFICIENT above.
_MIN_ANCHOR_FRACTION_FOR_SUFFICIENT = 0.5

# PR #15 fourth correction pass (2026-09-08, Blocker 4): descriptive
# target for how many FEASIBLE same-anchor candidates should exist
# beyond the top 3 (i.e. ~6 same-anchor feasible total: 3 shown + ~3
# reserve) when the provider genuinely has that many available. Never a
# hard requirement -- SYSTEM_POLICY treats reserve_depth_target_met as
# one more piece of evidence for the agent's own stop/continue
# judgment, same as every other observation field in this module.
_RESERVE_DEPTH_TARGET = 3


@dataclass(frozen=True)
class AnchorStats:
    """Deterministic, Python-only evidence of how well the LLM's OWN
    most recent anchor choice (AgentState.active_anchor_canonical) is
    represented among evaluated candidates. Never independently chooses
    or judges which pantry ingredient is "the" anchor -- that remains
    the LLM's call (DEC-005); this only reports how the search results
    reflect that choice, so the LLM can decide whether to keep
    searching, reformulate, or stop with genuine grounds."""

    anchor_canonical_id: str | None
    evaluated_count: int
    anchor_candidate_count: int
    feasible_anchor_candidate_count: int
    best_coverage_among_anchor_candidates: float | None
    best_coverage_among_non_anchor_candidates: float | None

    @property
    def anchor_candidate_fraction(self) -> float | None:
        if self.evaluated_count == 0:
            return None
        return self.anchor_candidate_count / self.evaluated_count

    @property
    def mostly_generic_overlap(self) -> bool:
        """True when an anchor is defined, at least one candidate has
        been evaluated, and fewer than half of them actually contain
        it -- the ticket's "results return mostly generic recipes...
        but not chicken wings" condition, expressed generically."""

        if self.anchor_canonical_id is None or self.evaluated_count == 0:
            return False
        return (self.anchor_candidate_fraction or 0.0) < _MIN_ANCHOR_FRACTION_FOR_SUFFICIENT


def candidate_contains_anchor(
    candidate: CandidateEvaluation,
    recipe_by_id: dict[str, Recipe],
    anchor_canonical_id: str | None,
) -> bool:
    """Single-candidate anchor-RELEVANCE check, factored out (PR #15
    second correction pass, 2026-09-08) so both the aggregate
    AnchorStats below and AgentOrchestrator's recommendations/
    additional_options/closest_alternatives partitioning use the exact
    same, single definition. Used ONLY for search-relevance
    display/observation purposes -- NEVER for pantry matching, missing-
    ingredient computation, cost, or pricing, which live entirely in
    app.domain.candidate_evaluation/cost_engine and compare canonical
    ids against the user's PANTRY, not the search anchor. This function
    is not called from, and has no path into, that code.

    True on either of two grounds:

    1. Exact canonical match -- the recipe has a normalized ingredient
       whose canonical_id equals the anchor exactly. The authoritative,
       always-correct signal.

    2. Grounded relevance fallback (PR #15 sixth correction pass,
       2026-09-08, live-audited): RecipeAPI.io's own ingredient
       taxonomy is sometimes coarser than a specific pantry ingredient
       -- e.g. "Ankara Pan-fried Lamb Cubes" and "Cop Shish Lamb Cubes
       Grilled" both genuinely are lamb-cube recipes by name, but their
       own ingredient records use "Lamb" and "Lamb leg" respectively,
       neither of which is "Lamb cubes". A candidate with no exact
       canonical match is still counted as anchor-relevant when the
       recipe's own TITLE contains the anchor's human-readable phrase
       (canonical id with underscores replaced by spaces, e.g.
       "lamb_cubes" -> "lamb cubes"), case-insensitively. This is a
       grounded, deterministic, generic string check against the
       recipe's own real title -- never free-form LLM semantic scoring,
       never an ingredient-specific branch, and it cannot make a
       generic "lamb" recipe count as a lamb_cubes match merely because
       it contains lamb (the title itself must contain the specific
       phrase "lamb cubes").

    Neither branch ever changes ownership/matched/missing ingredients,
    cost, pantry coverage, or pricing -- those remain governed
    exclusively by exact canonical_id equality elsewhere. False (not
    "unknown") whenever no anchor is defined or the recipe is
    unavailable, since an undefined anchor cannot be "contained"."""

    if anchor_canonical_id is None:
        return False
    recipe = recipe_by_id.get(candidate.recipe_id)
    if recipe is None:
        return False
    if any(ing.canonical_id == anchor_canonical_id for ing in recipe.ingredients):
        return True
    anchor_phrase = anchor_canonical_id.replace("_", " ")
    return anchor_phrase in (recipe.name or "").lower()


def compute_anchor_stats(
    candidates: list[CandidateEvaluation],
    recipe_by_id: dict[str, Recipe],
    anchor_canonical_id: str | None,
) -> AnchorStats:
    if anchor_canonical_id is None or not candidates:
        return AnchorStats(anchor_canonical_id, len(candidates), 0, 0, None, None)

    anchor_coverages: list[float] = []
    non_anchor_coverages: list[float] = []
    anchor_count = 0
    feasible_anchor_count = 0
    for candidate in candidates:
        has_anchor = candidate_contains_anchor(candidate, recipe_by_id, anchor_canonical_id)
        if has_anchor:
            anchor_count += 1
            anchor_coverages.append(candidate.pantry_coverage)
            if candidate.hard_constraint_pass:
                feasible_anchor_count += 1
        else:
            non_anchor_coverages.append(candidate.pantry_coverage)

    return AnchorStats(
        anchor_canonical_id=anchor_canonical_id,
        evaluated_count=len(candidates),
        anchor_candidate_count=anchor_count,
        feasible_anchor_candidate_count=feasible_anchor_count,
        best_coverage_among_anchor_candidates=max(anchor_coverages) if anchor_coverages else None,
        best_coverage_among_non_anchor_candidates=max(non_anchor_coverages) if non_anchor_coverages else None,
    )


@dataclass(frozen=True)
class ObservationCandidate:
    recipe_id: str
    provider: str
    name: str  # untrusted display text; never parsed as instructions
    cuisine_match: bool
    hard_constraint_pass: bool
    rejection_reasons: tuple[str, ...] = field(default_factory=tuple)
    # Post-review addition (2026-09-08): the LLM previously had no
    # visibility into HOW WELL a rejected candidate matched the pantry
    # -- only pass/fail. Without this, a batch of high-coverage
    # candidates rejected only for exceeding max_total_time_minutes
    # looked identical to a batch of genuinely poor matches, giving the
    # agent no signal to distinguish "reformulate the anchor" from
    # "this route/time constraint is just thin here." Already computed
    # deterministically by app.domain.pantry_matcher; exposing it here
    # adds no new calculation.
    pantry_coverage: float = 0.0


@dataclass(frozen=True)
class SearchObservation:
    attempt_number: int
    route: str
    strategy_summary: dict
    provider_error_category: str | None
    items_returned: int
    items_new: int
    items_evaluated_this_attempt: int
    feasible_count_this_attempt: int
    all_over_budget: bool
    all_strict_cuisine_mismatch: bool
    poor_pantry_overlap: bool
    has_more_pages: bool
    total_feasible_so_far: int
    total_evaluated_so_far: int
    candidate_cap_remaining: int
    search_attempts_remaining: int
    # Post-review addition (2026-09-08): mirrors all_over_budget /
    # all_strict_cuisine_mismatch, which already existed for those two
    # rejection categories -- max_total_time_minutes had no equivalent
    # aggregate signal, even though it is just as common a hard-reject
    # reason. Computed identically (see all_over_budget's own
    # docstring pattern in AgentOrchestrator._build_observation).
    # Placed after the non-default fields (dataclass field-ordering
    # requirement), not for any semantic reason.
    all_max_total_time_exceeded: bool = False
    top_candidates: tuple[ObservationCandidate, ...] = field(default_factory=tuple)
    # Priority 5 (PR #15 correction pass, 2026-09-08): per-attempt
    # anchor-relevance evidence (see AnchorStats/compute_anchor_stats
    # above) -- None fields mean no anchor was defined for this attempt
    # (e.g. an empty pantry), never a fabricated/guessed value.
    active_search_anchor: str | None = None
    anchor_candidates_this_attempt: int = 0
    feasible_anchor_candidates_this_attempt: int = 0
    best_coverage_among_anchor_candidates_this_attempt: float | None = None
    best_coverage_among_non_anchor_candidates_this_attempt: float | None = None
    mostly_generic_overlap_this_attempt: bool = False


def build_decision_payload(state: AgentState) -> dict:
    """Serialize state + the latest observation into the untrusted DATA
    block passed to LLMProvider.decide(). Only safe, high-level fields
    are included -- no hidden reasoning, no raw provider payloads.

    `pantry_canonical` is the minimum context a real model needs to
    choose a grounded search anchor (ticket section 9: "strongest
    pantry anchor ingredient") instead of inventing one. Canonical IDs
    are used rather than pantry_raw because they are already-normalized,
    machine-controlled vocabulary values (app.domain.grocery_taxonomy),
    not arbitrary free text -- the minimum safe context, per the
    independent review finding that fixed this (2026-09-07)."""

    observation = state.last_observation
    top_best_feasible = state.best_feasible[:MAX_FINAL_RECOMMENDATIONS]
    best_feasible_avg_coverage = (
        sum(c.pantry_coverage for c in top_best_feasible) / len(top_best_feasible) if top_best_feasible else 0.0
    )
    # Priority 5 (PR #15 correction pass, 2026-09-08): cumulative anchor
    # evidence across every candidate evaluated so far (any attempt/
    # anchor), scored against the CURRENT anchor -- if the LLM
    # reformulates to a different anchor, this recomputes fresh rather
    # than conflating two different anchors' evidence.
    anchor_stats = compute_anchor_stats(state.evaluated_candidates, state.recipe_by_id, state.active_anchor_canonical)
    return {
        "state_summary": {
            "pantry_canonical": sorted(state.pantry_canonical),
            "search_attempts_used": state.search_attempts,
            "search_attempts_remaining": max(0, state.max_search_attempts - state.search_attempts),
            "candidates_evaluated_total": len(state.evaluated_candidates),
            "candidate_cap_remaining": state.remaining_candidate_capacity(),
            "current_best_feasible_count": len(state.best_feasible),
            # Priority 5 additions: makes the LLM's own anchor choice's
            # real-world retrieval quality explicit and cumulative (never
            # Python's own classification of which ingredient matters --
            # see AnchorStats' docstring).
            "active_search_anchor": anchor_stats.anchor_canonical_id,
            "anchor_candidates_evaluated_total": anchor_stats.anchor_candidate_count,
            "anchor_candidate_fraction": anchor_stats.anchor_candidate_fraction,
            "feasible_anchor_candidates_total": anchor_stats.feasible_anchor_candidate_count,
            "best_coverage_among_anchor_candidates": anchor_stats.best_coverage_among_anchor_candidates,
            "best_coverage_among_non_anchor_candidates": anchor_stats.best_coverage_among_non_anchor_candidates,
            "mostly_generic_overlap": anchor_stats.mostly_generic_overlap,
            # PR #15 fourth correction pass (2026-09-08, Blocker 2 & 4):
            # whether a reviewed broader provider-search term exists for
            # the current anchor at all (app.recipe.provider.
            # PROVIDER_SEARCH_TERM_OVERRIDES -- e.g. true for
            # basmati_rice, false for chicken_wings, which deliberately
            # has no broader-parent entry), and whether it has already
            # been tried this run. Lets the agent judge whether
            # broadening is even an available lever before reaching for
            # it, and avoid repeating an already-tried broadening.
            "provider_broadening_available": (
                anchor_stats.anchor_canonical_id is not None
                and anchor_stats.anchor_canonical_id in PROVIDER_SEARCH_TERM_OVERRIDES
            ),
            "provider_broadening_already_used": state.active_anchor_broadening_used,
            # Blocker 4: reserve-depth evidence -- how many FEASIBLE
            # same-anchor candidates exist beyond what the top 3 already
            # need. Target is descriptive (~3, i.e. ~6 same-anchor
            # feasible total), never a hard requirement -- see
            # SYSTEM_POLICY for how the agent may use it.
            "same_anchor_reserve_count": max(
                0, anchor_stats.feasible_anchor_candidate_count - MAX_FINAL_RECOMMENDATIONS
            ),
            "reserve_depth_target_met": (
                anchor_stats.feasible_anchor_candidate_count - MAX_FINAL_RECOMMENDATIONS
            ) >= _RESERVE_DEPTH_TARGET,
            # Priority-1 efficiency fix (PR #15 correction pass,
            # 2026-09-08): explicit, unmissable boolean mirroring
            # MAX_FINAL_RECOMMENDATIONS -- SYSTEM_POLICY already said
            # "stop once enough strong feasible candidates exist" in
            # prose, but nothing forced the model to compare
            # current_best_feasible_count against the actual threshold
            # itself. This never overrides the LLM's stop decision
            # (DEC-005: the LLM controls stop conditions) -- it only
            # makes the deterministic evidence for that decision explicit
            # rather than implicit. Requires enough feasible candidates,
            # a minimum average pantry match among them (see
            # _MIN_AVERAGE_COVERAGE_FOR_SUFFICIENT), AND -- Priority 5 --
            # when an anchor is defined and anchor matches exist at all,
            # enough of those feasible candidates actually contain the
            # anchor and the pool isn't mostly generic overlap. Feasible
            # alone (hard_constraint_pass) says nothing about relevance;
            # coverage alone says nothing about WHY it's low.
            "sufficient_feasible_found": (
                len(state.best_feasible) >= MAX_FINAL_RECOMMENDATIONS
                and best_feasible_avg_coverage >= _MIN_AVERAGE_COVERAGE_FOR_SUFFICIENT
                and (
                    anchor_stats.anchor_canonical_id is None
                    or anchor_stats.anchor_candidate_count == 0
                    or (
                        anchor_stats.feasible_anchor_candidate_count >= MAX_FINAL_RECOMMENDATIONS
                        and not anchor_stats.mostly_generic_overlap
                    )
                )
            ),
            "cuisine_preference": state.cuisine_preference,
            "cuisine_strict": state.cuisine_strict,
            "budget_set": state.budget_aed is not None,
            "max_total_time_set": state.max_total_time_minutes is not None,
            "provider_status": dict(state.provider_status),
        },
        "latest_search_observation": asdict(observation) if observation is not None else None,
    }
