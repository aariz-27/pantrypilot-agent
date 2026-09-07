"""Standalone AgentAction schema security tests (ticket section 7:
"Action schema must make invalid actions impossible or safely reject
them.").

These are pure schema-validation tests, independent of the
orchestrator loop -- they prove the boundary is enforced at the type
level, not merely by orchestrator-side convention.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agent.actions import ActionType, AgentAction, PaginateArgs, RetryArgs, SearchArgs, SearchRoute, StopArgs, StopReason


def test_search_action_requires_matching_search_args():
    with pytest.raises(ValidationError):
        AgentAction(action_type=ActionType.SEARCH)


def test_search_action_rejects_mismatched_args():
    with pytest.raises(ValidationError):
        AgentAction(action_type=ActionType.STOP, search=SearchArgs(route=SearchRoute.RECIPEAPI_IO, anchor_ingredients=["tomato"]))


def test_search_args_rejects_extra_fields():
    with pytest.raises(ValidationError):
        SearchArgs.model_validate(
            {"route": "recipeapi_io", "anchor_ingredients": ["tomato"], "budget_aed": 5}
        )


def test_search_args_rejects_empty_anchor_list():
    with pytest.raises(ValidationError):
        SearchArgs(route=SearchRoute.RECIPEAPI_IO, anchor_ingredients=[])


def test_search_args_rejects_blank_only_anchor_list():
    with pytest.raises(ValidationError):
        SearchArgs(route=SearchRoute.RECIPEAPI_IO, anchor_ingredients=["   ", ""])


def test_search_args_caps_anchor_list_length():
    with pytest.raises(ValidationError):
        SearchArgs(route=SearchRoute.RECIPEAPI_IO, anchor_ingredients=["a", "b", "c", "d", "e"])


def test_agent_action_rejects_unknown_action_type():
    with pytest.raises(ValidationError):
        AgentAction.model_validate({"action_type": "delete_everything"})


def test_agent_action_rejects_top_level_extra_fields():
    with pytest.raises(ValidationError):
        AgentAction.model_validate(
            {
                "action_type": "stop",
                "stop": {"reason": "sufficient_feasible_candidates"},
                "budget_aed": 1,
            }
        )


def test_stop_args_rejects_extra_fields():
    with pytest.raises(ValidationError):
        StopArgs.model_validate({"reason": "sufficient_feasible_candidates", "excluded_canonical": ["tomato"]})


def test_valid_search_action_round_trips():
    action = AgentAction(
        action_type=ActionType.SEARCH,
        search=SearchArgs(route=SearchRoute.RECIPEAPI_IO, anchor_ingredients=["tomato", "onion"], cuisine="Italian"),
    )
    dumped = action.model_dump(mode="json")
    restored = AgentAction.model_validate(dumped)
    assert restored == action


def test_valid_paginate_and_retry_and_stop_actions_round_trip():
    for action in (
        AgentAction(action_type=ActionType.PAGINATE, paginate=PaginateArgs()),
        AgentAction(action_type=ActionType.RETRY, retry=RetryArgs()),
        AgentAction(action_type=ActionType.STOP, stop=StopArgs(reason=StopReason.ATTEMPT_LIMIT_REACHED)),
    ):
        assert AgentAction.model_validate(action.model_dump(mode="json")) == action


def test_action_schema_has_no_free_form_rationale_field():
    """rationale_category must always be a closed enum -- there is no
    free-text reasoning channel anywhere in the schema (ticket section
    6: no hidden chain-of-thought; section 16: category, not prose)."""

    schema = AgentAction.model_json_schema()
    defs = schema.get("$defs", {})
    for name, definition in defs.items():
        if "rationale_category" in definition.get("properties", {}):
            prop = definition["properties"]["rationale_category"]
            # allOf/$ref or anyOf pointing at the closed RationaleCategory enum,
            # never a bare "type": "string" free-text field.
            assert "type" not in prop or prop.get("type") != "string", name
