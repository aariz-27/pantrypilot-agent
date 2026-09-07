"""Bounded, typed agent action set (TECHNICAL_SPEC.md section 4, "Tools").

The LLM chooses only from this fixed action set. There is deliberately
no field anywhere in this schema for a budget, exclusion list, cuisine
strictness flag, time limit, recipe name/ingredients/instructions, or a
free-form numeric score -- the LLM cannot request or express any of
those things even maliciously, because the schema has no place to put
them (ticket section 7: "Action schema must make invalid actions
impossible or safely reject them."). `extra="forbid"` additionally
rejects any unexpected key outright rather than silently ignoring it.

`rationale_category` is a closed enum, never free text, so no channel
exists for hidden chain-of-thought or smuggled content (ticket section
16: "Structured action + optional short machine-safe rationale/category
is sufficient").

Reformulation is not a separate action type: a materially different
SEARCH is a reformulation; an identical SEARCH is rejected by the
orchestrator's policy layer (app.agent.tools) unless the caller uses
RETRY (same strategy, only after a transient provider failure) or
PAGINATE (same strategy, next page).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ActionType(str, Enum):
    SEARCH = "search"
    PAGINATE = "paginate"
    RETRY = "retry"
    STOP = "stop"


class RationaleCategory(str, Enum):
    NO_RESULTS = "no_results"
    WEAK_PANTRY_OVERLAP = "weak_pantry_overlap"
    ALL_OVER_BUDGET = "all_over_budget"
    ALL_HARD_CONSTRAINT_FAILURES = "all_hard_constraint_failures"
    CUISINE_MISMATCH = "cuisine_mismatch"
    RESULTS_INSUFFICIENT_QUERY_RELEVANT = "results_insufficient_query_relevant"
    SUFFICIENT_FEASIBLE_CANDIDATES = "sufficient_feasible_candidates"
    ATTEMPT_LIMIT_REACHED = "attempt_limit_reached"
    PROVIDER_ERROR_TRANSIENT = "provider_error_transient"
    PROVIDER_UNAVAILABLE_NO_FALLBACK = "provider_unavailable_no_fallback"
    INPUT_MAKES_SEARCH_IMPOSSIBLE = "input_makes_search_impossible"
    NO_MATERIALLY_DIFFERENT_STRATEGY_REMAINS = "no_materially_different_strategy_remains"
    OTHER = "other"


class SearchRoute(str, Enum):
    RECIPEAPI_IO = "recipeapi_io"
    LOCAL_CURATED = "local_curated"


class SearchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    route: SearchRoute
    anchor_ingredients: list[str] = Field(min_length=1, max_length=4)
    cuisine: str | None = Field(default=None, max_length=50)
    rationale_category: RationaleCategory | None = None

    @field_validator("anchor_ingredients")
    @classmethod
    def _clean_anchors(cls, value: list[str]) -> list[str]:
        cleaned = [v.strip() for v in value if v and v.strip()]
        if not cleaned:
            raise ValueError("anchor_ingredients must contain at least one non-blank item")
        return cleaned


class PaginateArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rationale_category: RationaleCategory | None = None


class RetryArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rationale_category: RationaleCategory | None = None


class StopReason(str, Enum):
    SUFFICIENT_FEASIBLE_CANDIDATES = "sufficient_feasible_candidates"
    ATTEMPT_LIMIT_REACHED = "attempt_limit_reached"
    INPUT_MAKES_SEARCH_IMPOSSIBLE = "input_makes_search_impossible"
    PROVIDER_UNAVAILABLE_NO_FALLBACK = "provider_unavailable_no_fallback"
    NO_MATERIALLY_DIFFERENT_STRATEGY_REMAINS = "no_materially_different_strategy_remains"


class StopArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reason: StopReason
    rationale_category: RationaleCategory | None = None


class AgentAction(BaseModel):
    """The single wire-level shape the LLM must return. Exactly one of
    the four args fields is populated, matching `action_type`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    action_type: ActionType
    search: SearchArgs | None = None
    paginate: PaginateArgs | None = None
    retry: RetryArgs | None = None
    stop: StopArgs | None = None

    @model_validator(mode="after")
    def _args_match_action_type(self) -> "AgentAction":
        slots = {
            ActionType.SEARCH: self.search,
            ActionType.PAGINATE: self.paginate,
            ActionType.RETRY: self.retry,
            ActionType.STOP: self.stop,
        }
        for action_type, args in slots.items():
            if action_type == self.action_type:
                if args is None:
                    raise ValueError(f"action_type={action_type.value} requires matching '{action_type.value}' args")
            elif args is not None:
                raise ValueError(
                    f"'{action_type.value}' args must not be set when action_type={self.action_type.value}"
                )
        return self


TOOL_NAME = "pantrypilot_agent_decision"
TOOL_DESCRIPTION = (
    "Choose the next PantryPilot recipe-search action. Return exactly one "
    "of: search (a new or materially different strategy), paginate (next "
    "page of the immediately preceding strategy), retry (re-issue the "
    "immediately preceding strategy only after a transient provider "
    "failure), or stop (with a reason)."
)
