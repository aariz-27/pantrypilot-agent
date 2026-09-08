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

from app.agent.state import AgentState

# Bound the number of individual candidates surfaced to the model --
# the agent needs aggregate signals to decide, not a full listing
# (ticket section 10: "Do not expose unnecessary raw/internal details").
_MAX_OBSERVED_CANDIDATES = 5


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
    return {
        "state_summary": {
            "pantry_canonical": sorted(state.pantry_canonical),
            "search_attempts_used": state.search_attempts,
            "search_attempts_remaining": max(0, state.max_search_attempts - state.search_attempts),
            "candidates_evaluated_total": len(state.evaluated_candidates),
            "candidate_cap_remaining": state.remaining_candidate_capacity(),
            "current_best_feasible_count": len(state.best_feasible),
            "cuisine_preference": state.cuisine_preference,
            "cuisine_strict": state.cuisine_strict,
            "budget_set": state.budget_aed is not None,
            "max_total_time_set": state.max_total_time_minutes is not None,
            "provider_status": dict(state.provider_status),
        },
        "latest_search_observation": asdict(observation) if observation is not None else None,
    }
