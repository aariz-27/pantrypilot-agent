"""Module E: POST /api/recommend integration tests.

Uses a fake AgentOrchestrator (dependency override) -- no live Anthropic
or RecipeAPI.io calls, consistent with docs/AGENTS.md ("Use mocks for
routine provider/API tests"). The orchestrator itself is already
covered by tests/agent/test_orchestrator_scenarios.py; these tests
cover the HTTP boundary: request validation and response mapping.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.agent.actions import ActionType, AgentAction, SearchArgs, SearchRoute, StopArgs, StopReason
from app.agent.errors import AgentMalformedActionError
from app.agent.orchestrator import AgentOrchestrator, AgentResult
from app.api.recommend import get_orchestrator
from app.config import Settings, get_settings
from app.domain.cost_engine import IngredientCostDetail, MissingIngredientBreakdown
from app.domain.models import CandidateEvaluation, CostConfidence, Difficulty, Recipe, RejectionReason, RecipeIngredient
from app.domain.serving_scaler import ScaledRecipe
from app.main import app
from app.repositories.price_repository import PriceRepository

from tests.agent.conftest import FakeLLMProvider, FakeRecipeProvider, ScriptedSearch, make_recipe, price_db  # noqa: F401 -- fixture

VALID_REQUEST = {
    "ingredients": ["chicken", "rice", "onion", "garlic"],
    "servings": 4,
    "max_total_time_minutes": 45,
}


def _recipe(**overrides) -> Recipe:
    defaults = dict(
        id="recipeapi_io:1",
        provider="recipeapi_io",
        provider_recipe_id="1",
        name="Chicken Fried Rice",
        cuisine="Asian",
        image_url="https://example.test/img.jpg",
        source_url="https://example.test/recipe/1",
        difficulty=Difficulty.EASY,
        servings=2,
        prep_time_minutes=10,
        cook_time_minutes=15,
        instructions="Step 1. Step 2.",
    )
    defaults.update(overrides)
    return Recipe(**defaults)


def _candidate(**overrides) -> CandidateEvaluation:
    defaults = dict(
        recipe_id="recipeapi_io:1",
        provider="recipeapi_io",
        pantry_coverage=0.75,
        matched_ingredients=["chicken_breast", "rice", "onion"],
        missing_ingredients=["soy_sauce"],
        missing_count=1,
        estimated_purchase_cost_aed=3.5,
        price_complete=True,
        cost_confidence=CostConfidence.HIGH,
        cuisine_match=True,
        hard_constraint_pass=True,
        rejection_reasons=[],
        deterministic_score=0.9,
    )
    defaults.update(overrides)
    return CandidateEvaluation(**defaults)


class FakeOrchestrator:
    def __init__(self, result: AgentResult | Exception) -> None:
        self._result = result

    async def run(self, request):
        self.request = request
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _override(fake_orchestrator: FakeOrchestrator) -> None:
    app.dependency_overrides[get_orchestrator] = lambda: fake_orchestrator


def _clear() -> None:
    app.dependency_overrides.clear()


def _happy_path_result() -> AgentResult:
    recipe = _recipe()
    candidate = _candidate()
    breakdown = [
        MissingIngredientBreakdown(
            raw_name="soy sauce",
            canonical_id="soy_sauce",
            normalized_unit="ml",
            scaled_required_quantity=100.0,
            detail=IngredientCostDetail(
                canonical_id="soy_sauce",
                packages_needed=1,
                package_price_aed=3.5,
                line_cost_aed=3.5,
                price_complete=True,
                cost_confidence=CostConfidence.HIGH,
            ),
        )
    ]
    scaling = ScaledRecipe(recipe=recipe, requested_servings=4, original_servings=2, scaling_applied=True, scaling_factor=2.0)
    return AgentResult(
        request_id="req_test123",
        status="completed",
        search_attempts=1,
        recommendations=[candidate],
        closest_alternatives=[],
        stop_reason="sufficient_feasible_candidates",
        progress_events=["attempt 1: route=recipeapi_io new_items=1 feasible=1"],
        provider_status={"recipeapi_io": "ok"},
        recipe_by_id={recipe.id: recipe},
        scaling_by_id={recipe.id: scaling},
        missing_breakdown_by_id={recipe.id: breakdown},
        pantry_unresolved=[],
    )


def test_happy_path_returns_mapped_recipe_card():
    _override(FakeOrchestrator(_happy_path_result()))
    try:
        client = TestClient(app)
        response = client.post("/api/recommend", json=VALID_REQUEST)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "completed"
        assert len(body["recommendations"]) == 1
        card = body["recommendations"][0]
        assert card["name"] == "Chicken Fried Rice"
        assert card["difficulty"] == "easy"
        assert card["is_exact_match"] is True
        assert card["deviation_reasons"] == []
        assert card["provider_original_servings"] == 2
        assert card["requested_servings"] == 4
        assert card["servings_scaling_applied"] is True
        assert card["total_time_minutes"] == 25
        assert card["missing_ingredients"][0]["display_name"] == "Soy Sauce"
        assert card["missing_ingredients"][0]["estimated_cost_aed"] == 3.5
        assert card["estimated_additional_spend_aed"] == 3.5
    finally:
        _clear()


def test_unknown_price_is_never_returned_as_zero():
    result = _happy_path_result()
    incomplete_breakdown = [
        MissingIngredientBreakdown(
            raw_name="saffron",
            canonical_id="saffron",
            normalized_unit=None,
            scaled_required_quantity=None,
            detail=IngredientCostDetail(None, None, None, None, False, CostConfidence.UNKNOWN),
        )
    ]
    result.missing_breakdown_by_id[result.recommendations[0].recipe_id] = incomplete_breakdown
    _override(FakeOrchestrator(result))
    try:
        client = TestClient(app)
        response = client.post("/api/recommend", json=VALID_REQUEST)
        row = response.json()["recommendations"][0]["missing_ingredients"][0]
        assert row["price_complete"] is False
        assert row["estimated_cost_aed"] is None
    finally:
        _clear()


def test_closest_alternative_reports_time_deviation():
    recipe = _recipe(prep_time_minutes=30, cook_time_minutes=27)
    candidate = _candidate(hard_constraint_pass=False, rejection_reasons=[RejectionReason.MAX_TOTAL_TIME_EXCEEDED])
    scaling = ScaledRecipe(recipe=recipe, requested_servings=4, original_servings=2, scaling_applied=True, scaling_factor=2.0)
    result = AgentResult(
        request_id="req_x",
        status="no_feasible_match",
        search_attempts=3,
        recommendations=[],
        closest_alternatives=[candidate],
        stop_reason="attempt_limit_reached",
        progress_events=[],
        provider_status={},
        recipe_by_id={recipe.id: recipe},
        scaling_by_id={recipe.id: scaling},
        missing_breakdown_by_id={recipe.id: []},
        pantry_unresolved=[],
    )
    _override(FakeOrchestrator(result))
    try:
        client = TestClient(app)
        response = client.post("/api/recommend", json=VALID_REQUEST)
        card = response.json()["closest_alternatives"][0]
        assert card["is_exact_match"] is False
        assert card["deviation_reasons"] == ["12 min over your target"]
    finally:
        _clear()


def test_excluded_ingredient_violation_never_shown_as_closest_alternative():
    recipe = _recipe()
    candidate = _candidate(hard_constraint_pass=False, rejection_reasons=[RejectionReason.EXCLUDED_INGREDIENT_PRESENT])
    result = AgentResult(
        request_id="req_x",
        status="no_feasible_match",
        search_attempts=3,
        recommendations=[],
        closest_alternatives=[candidate],
        stop_reason="attempt_limit_reached",
        progress_events=[],
        provider_status={},
        recipe_by_id={recipe.id: recipe},
        scaling_by_id={},
        missing_breakdown_by_id={recipe.id: []},
        pantry_unresolved=[],
    )
    _override(FakeOrchestrator(result))
    try:
        client = TestClient(app)
        response = client.post("/api/recommend", json=VALID_REQUEST)
        assert response.json()["closest_alternatives"] == []
    finally:
        _clear()


def test_unresolved_ingredients_carry_a_stable_identity_key_across_cards():
    # Priority-3 (PR #15 correction pass, 2026-09-08): the frontend needs
    # a safe, deterministic way to recognize the SAME unresolved raw
    # ingredient across multiple displayed cards when the user confirms
    # they already own it -- never a canonical_id, never taxonomy
    # promotion.
    recipe_a = _recipe(id="recipeapi_io:1", provider_recipe_id="1")
    recipe_b = _recipe(id="recipeapi_io:2", provider_recipe_id="2", name="Other Dish")
    candidate_a = _candidate(recipe_id="recipeapi_io:1", unresolved_ingredients=["  Special Sauce X!! "])
    candidate_b = _candidate(recipe_id="recipeapi_io:2", unresolved_ingredients=["special sauce x"])
    result = AgentResult(
        request_id="req_x",
        status="completed",
        search_attempts=1,
        recommendations=[candidate_a, candidate_b],
        closest_alternatives=[],
        stop_reason="sufficient_feasible_candidates",
        progress_events=[],
        provider_status={},
        recipe_by_id={recipe_a.id: recipe_a, recipe_b.id: recipe_b},
        scaling_by_id={},
        missing_breakdown_by_id={recipe_a.id: [], recipe_b.id: []},
        pantry_unresolved=[],
    )
    _override(FakeOrchestrator(result))
    try:
        client = TestClient(app)
        response = client.post("/api/recommend", json=VALID_REQUEST)
        body = response.json()
        card_a, card_b = body["recommendations"]
        row_a = card_a["unresolved_ingredients"][0]
        row_b = card_b["unresolved_ingredients"][0]
        assert row_a["raw_name"] == "  Special Sauce X!! "
        assert row_a["identity_key"] == row_b["identity_key"] == "special sauce x"
    finally:
        _clear()


def test_pantry_unresolved_is_surfaced():
    result = _happy_path_result()
    result.pantry_unresolved.append("kohlrabi")
    _override(FakeOrchestrator(result))
    try:
        client = TestClient(app)
        response = client.post("/api/recommend", json=VALID_REQUEST)
        body = response.json()
        assert body["pantry_unresolved"] == ["kohlrabi"]
        assert any("1 pantry ingredient" in limitation for limitation in body["limitations"])
    finally:
        _clear()


def test_higher_match_time_excluded_is_surfaced_as_deterministic_summary_only():
    result = _happy_path_result()
    result = result.__class__(
        **{**result.__dict__, "higher_match_time_excluded": True, "higher_match_time_excluded_count": 2, "higher_match_min_rejected_time_minutes": 45},
    )
    _override(FakeOrchestrator(result))
    try:
        client = TestClient(app)
        response = client.post("/api/recommend", json=VALID_REQUEST)
        body = response.json()
        assert body["higher_match_time_excluded"] is True
        assert body["higher_match_time_excluded_count"] == 2
        assert body["higher_match_min_rejected_time_minutes"] == 45
        # Deterministic summary data only -- never raw agent internals.
        assert "system_policy" not in response.text
        assert "chain_of_thought" not in response.text
    finally:
        _clear()


def test_higher_match_time_excluded_defaults_false():
    _override(FakeOrchestrator(_happy_path_result()))
    try:
        client = TestClient(app)
        response = client.post("/api/recommend", json=VALID_REQUEST)
        body = response.json()
        assert body["higher_match_time_excluded"] is False
        assert body["higher_match_time_excluded_count"] == 0
        assert body["higher_match_min_rejected_time_minutes"] is None
    finally:
        _clear()


def test_agent_malformed_action_error_maps_to_503():
    _override(FakeOrchestrator(AgentMalformedActionError("bad output")))
    try:
        client = TestClient(app)
        response = client.post("/api/recommend", json=VALID_REQUEST)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "AGENT_MALFORMED_ACTION"
    finally:
        _clear()


def test_unsupported_action_error_still_gets_a_safe_structured_envelope_if_it_ever_leaked():
    # Defense in depth only, NOT the ticket's normal-path fix: under the
    # fixed orchestrator (see tests/agent/test_orchestrator_scenarios.py
    # and test_invalid_grounded_anchor_rejection_recovers_and_returns_200_not_500
    # below), AgentUnsupportedActionError is always caught and recovered
    # from INSIDE AgentOrchestrator.run for every normal agent search
    # path and never reaches this HTTP boundary. docs/API_INTEGRATION_
    # STANDARDS.md section 11 reserves 500 for "unexpected internal
    # failure" -- a leak here (the orchestration-level fix being bypassed
    # or removed) is exactly that, so the mapping intentionally stays
    # 500, unchanged by this ticket. What this test actually guards is
    # that such a leak still returns PantryPilotError's SAFE structured
    # envelope (typed code/message/retryable, no stack trace) rather
    # than a raw unhandled crash -- confirming the existing global
    # handler in app.main still applies to this error type.
    from app.agent.errors import AgentUnsupportedActionError

    _override(FakeOrchestrator(AgentUnsupportedActionError("search anchor 'lamb' is not present in the user's pantry")))
    try:
        client = TestClient(app)
        response = client.post("/api/recommend", json=VALID_REQUEST)
        assert response.status_code == 500
        body = response.json()
        assert body["error"]["code"] == "AGENT_UNSUPPORTED_ACTION"
        assert "Traceback" not in response.text
    finally:
        _clear()


def test_invalid_grounded_anchor_rejection_recovers_and_returns_200_not_500(price_db):
    """End-to-end regression for the PR #15 live defect: Claude proposes
    a search anchor broader than the user's actual pantry item (here,
    "lamb" when the pantry only has "minced_lamb", mirroring the exact
    live repro in the ticket). The deterministic grounding guard must
    still reject it (never weakened), but the orchestrator must recover
    via corrective retry and the API must return a normal 200 response
    -- never the HTTP 500 this ticket fixes. Uses the REAL
    AgentOrchestrator (not FakeOrchestrator) so the actual internal
    recovery path in app.agent.orchestrator.run is exercised end to end
    through the HTTP boundary."""

    from app.recipe.provider import SearchResult, SearchResultItem

    recipe = make_recipe(
        id="recipeapi_io:1", provider_recipe_id="1", name="Minced Lamb Kebabs",
        prep_time_minutes=10, cook_time_minutes=20,
        ingredients=[RecipeIngredient(raw_name="minced lamb", raw_measure="200 g")],
    )
    search_result = SearchResult(
        items=[SearchResultItem(id="recipeapi_io:1", provider="recipeapi_io", provider_recipe_id="1", name=recipe.name)],
        page=1,
        page_size=10,
        has_more=False,
    )
    provider = FakeRecipeProvider(
        "recipeapi_io", searches=[ScriptedSearch(result=search_result)], details_by_id={"1": recipe}
    )
    llm = FakeLLMProvider(
        [
            AgentAction(
                action_type=ActionType.SEARCH,
                search=SearchArgs(route=SearchRoute.RECIPEAPI_IO, anchor_ingredients=["lamb"]),
            ),
            AgentAction(
                action_type=ActionType.SEARCH,
                search=SearchArgs(route=SearchRoute.RECIPEAPI_IO, anchor_ingredients=["minced lamb"]),
            ),
            AgentAction(
                action_type=ActionType.STOP,
                stop=StopArgs(reason=StopReason.SUFFICIENT_FEASIBLE_CANDIDATES),
            ),
        ]
    )
    orchestrator = AgentOrchestrator(llm, {"recipeapi_io": provider}, PriceRepository(price_db))
    _override(orchestrator)
    try:
        client = TestClient(app)
        response = client.post(
            "/api/recommend",
            json={"ingredients": ["minced lamb"], "servings": 4, "max_total_time_minutes": 45},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "completed"
        assert body["recommendations"][0]["recipe_id"] == "recipeapi_io:1"
        # The rejected "lamb" anchor never reached the provider -- only
        # the corrective, grounded "minced lamb" search did.
        assert len(provider.search_calls) == 1
        # 2026-09-13: grounded provider term (space, not underscore).
        assert provider.search_calls[0].query_ingredients == ["minced lamb"]
    finally:
        _clear()


# --- request validation -------------------------------------------------------------


def test_invalid_body_is_still_422_even_when_providers_are_unconfigured():
    # Regression test for the CI failure found in independent review
    # (2026-09-08): FastAPI resolves Depends() sub-dependencies before
    # validating the request body. get_llm_provider/get_orchestrator
    # used to construct AnthropicLLMProvider unconditionally, which
    # raised LLMProviderConfigurationError whenever the LLM wasn't
    # configured (exactly CI's state -- no credentials) -- masking a
    # structurally invalid request's correct 422 with a 503 instead.
    # This must return 422 regardless of provider configuration.
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    try:
        client = TestClient(app)
        payload = {k: v for k, v in VALID_REQUEST.items() if k != "servings"}
        response = client.post("/api/recommend", json=payload)
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_missing_servings_is_rejected():
    payload = {k: v for k, v in VALID_REQUEST.items() if k != "servings"}
    client = TestClient(app)
    response = client.post("/api/recommend", json=payload)
    assert response.status_code == 422


def test_missing_total_time_is_rejected():
    payload = {k: v for k, v in VALID_REQUEST.items() if k != "max_total_time_minutes"}
    client = TestClient(app)
    response = client.post("/api/recommend", json=payload)
    assert response.status_code == 422


def test_empty_ingredients_list_is_rejected():
    payload = {**VALID_REQUEST, "ingredients": []}
    client = TestClient(app)
    response = client.post("/api/recommend", json=payload)
    assert response.status_code == 422


def test_too_many_ingredients_is_rejected():
    payload = {**VALID_REQUEST, "ingredients": [f"item{i}" for i in range(31)]}
    client = TestClient(app)
    response = client.post("/api/recommend", json=payload)
    assert response.status_code == 422


def test_servings_out_of_bounds_is_rejected():
    for bad in (0, 21):
        payload = {**VALID_REQUEST, "servings": bad}
        client = TestClient(app)
        response = client.post("/api/recommend", json=payload)
        assert response.status_code == 422


def test_total_time_out_of_bounds_is_rejected():
    for bad in (0, 601):
        payload = {**VALID_REQUEST, "max_total_time_minutes": bad}
        client = TestClient(app)
        response = client.post("/api/recommend", json=payload)
        assert response.status_code == 422


def test_negative_budget_is_rejected():
    payload = {**VALID_REQUEST, "budget_aed": -1}
    client = TestClient(app)
    response = client.post("/api/recommend", json=payload)
    assert response.status_code == 422


def test_too_many_excluded_ingredients_is_rejected():
    payload = {**VALID_REQUEST, "excluded_ingredients": [f"item{i}" for i in range(21)]}
    client = TestClient(app)
    response = client.post("/api/recommend", json=payload)
    assert response.status_code == 422


def test_unknown_privileged_field_is_rejected():
    payload = {**VALID_REQUEST, "deterministic_score": 0.99}
    client = TestClient(app)
    response = client.post("/api/recommend", json=payload)
    assert response.status_code == 422


def test_unconfigured_llm_provider_fails_safely_with_503_not_a_crash(tmp_path):
    # Real dependency chain (get_orchestrator -> get_llm_provider ->
    # AnthropicLLMProvider(settings)), not the FakeOrchestrator override
    # -- this proves a configuration error raised during FastAPI
    # dependency resolution itself is still caught by the global
    # PantryPilotError handler rather than surfacing as an unhandled 500.
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, price_db_path=str(tmp_path / "unused.db")
    )
    try:
        client = TestClient(app)
        response = client.post("/api/recommend", json=VALID_REQUEST)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "LLM_PROVIDER_CONFIGURATION_ERROR"
    finally:
        app.dependency_overrides.clear()


def test_valid_request_passes_allow_hard_difficulty_through():
    fake = FakeOrchestrator(_happy_path_result())
    _override(fake)
    try:
        client = TestClient(app)
        client.post("/api/recommend", json={**VALID_REQUEST, "allow_hard_difficulty": True})
        assert fake.request.allow_hard_difficulty is True
    finally:
        _clear()


def test_additional_options_are_mapped_into_the_response():
    recipe_a = _recipe(id="recipeapi_io:1", provider_recipe_id="1")
    recipe_b = _recipe(id="recipeapi_io:2", provider_recipe_id="2", name="Reserve Dish")
    candidate_a = _candidate(recipe_id="recipeapi_io:1")
    candidate_b = _candidate(recipe_id="recipeapi_io:2")
    result = AgentResult(
        request_id="req_x",
        status="completed",
        search_attempts=1,
        recommendations=[candidate_a],
        additional_options=[candidate_b],
        closest_alternatives=[],
        stop_reason="sufficient_feasible_candidates",
        progress_events=[],
        provider_status={},
        recipe_by_id={recipe_a.id: recipe_a, recipe_b.id: recipe_b},
        scaling_by_id={},
        missing_breakdown_by_id={recipe_a.id: [], recipe_b.id: []},
        pantry_unresolved=[],
    )
    _override(FakeOrchestrator(result))
    try:
        client = TestClient(app)
        response = client.post("/api/recommend", json=VALID_REQUEST)
        body = response.json()
        assert len(body["recommendations"]) == 1
        assert len(body["additional_options"]) == 1
        assert body["additional_options"][0]["name"] == "Reserve Dish"
        assert body["additional_options"][0]["is_exact_match"] is True
    finally:
        _clear()


def test_additional_options_defaults_to_empty_list():
    result = _happy_path_result()
    _override(FakeOrchestrator(result))
    try:
        client = TestClient(app)
        response = client.post("/api/recommend", json=VALID_REQUEST)
        assert response.json()["additional_options"] == []
    finally:
        _clear()


def test_contains_active_anchor_is_mapped_into_the_response():
    recipe_a = _recipe(id="recipeapi_io:1", provider_recipe_id="1")
    recipe_b = _recipe(id="recipeapi_io:2", provider_recipe_id="2", name="Reserve Dish")
    candidate_a = _candidate(recipe_id="recipeapi_io:1")
    candidate_b = _candidate(recipe_id="recipeapi_io:2")
    result = AgentResult(
        request_id="req_x",
        status="completed",
        search_attempts=1,
        recommendations=[candidate_a],
        additional_options=[candidate_b],
        closest_alternatives=[],
        stop_reason="sufficient_feasible_candidates",
        progress_events=[],
        provider_status={},
        recipe_by_id={recipe_a.id: recipe_a, recipe_b.id: recipe_b},
        scaling_by_id={},
        missing_breakdown_by_id={recipe_a.id: [], recipe_b.id: []},
        pantry_unresolved=[],
        anchor_match_by_id={"recipeapi_io:1": True, "recipeapi_io:2": False},
    )
    _override(FakeOrchestrator(result))
    try:
        client = TestClient(app)
        response = client.post("/api/recommend", json=VALID_REQUEST)
        body = response.json()
        assert body["recommendations"][0]["contains_active_anchor"] is True
        assert body["additional_options"][0]["contains_active_anchor"] is False
    finally:
        _clear()


def test_contains_active_anchor_defaults_to_none_when_no_anchor_tracked():
    result = _happy_path_result()
    _override(FakeOrchestrator(result))
    try:
        client = TestClient(app)
        response = client.post("/api/recommend", json=VALID_REQUEST)
        assert response.json()["recommendations"][0]["contains_active_anchor"] is None
    finally:
        _clear()


# -- cuisine/RecipeAPI enum alignment (2026-09-13) --------------------------


def test_strict_cuisine_accepts_every_supported_value():
    from app.rate_limit import limiter
    from app.recipe.provider import SUPPORTED_STRICT_CUISINES

    fake = FakeOrchestrator(_happy_path_result())
    _override(fake)
    try:
        client = TestClient(app)
        for cuisine in sorted(SUPPORTED_STRICT_CUISINES):
            limiter.reset()  # 11 supported cuisines exceed the 10/minute /recommend limit otherwise
            response = client.post(
                "/api/recommend", json={**VALID_REQUEST, "cuisine": cuisine, "cuisine_strict": True}
            )
            assert response.status_code == 200, (cuisine, response.text)
            assert fake.request.cuisine_preference == cuisine
            assert fake.request.cuisine_strict is True
    finally:
        _clear()


def test_strict_cuisine_accepts_title_cased_supported_value_case_insensitively():
    # The frontend submits the display label ("Italian"), not the
    # lowercase canonical form -- validation must not require callers
    # to pre-lowercase.
    _override(FakeOrchestrator(_happy_path_result()))
    try:
        client = TestClient(app)
        response = client.post("/api/recommend", json={**VALID_REQUEST, "cuisine": "Italian", "cuisine_strict": True})
        assert response.status_code == 200
    finally:
        _clear()


def test_strict_cuisine_rejects_unsupported_values():
    # No custom RequestValidationError handler is registered (matches
    # every other 422 in this file, e.g. test_missing_servings_is_rejected
    # -- none inspect the body shape) -- FastAPI's default
    # {"detail": [...]} envelope applies, not the PantryPilotError
    # {"error": {...}} shape (that handler only fires for a raised
    # PantryPilotError, never a Pydantic ValidationError).
    client = TestClient(app)
    for unsupported in ("Indian", "Pakistani", "Asian", "Mediterranean", "indian"):
        response = client.post(
            "/api/recommend", json={**VALID_REQUEST, "cuisine": unsupported, "cuisine_strict": True}
        )
        assert response.status_code == 422, unsupported
        assert "not a supported cuisine" in response.json()["detail"][0]["msg"]


def test_strict_cuisine_rejection_never_reaches_the_orchestrator():
    # Do not silently send an unsupported cuisine to RecipeAPI.io --
    # confirmed here by proving the (fake, but request-recording)
    # orchestrator is never even invoked for a rejected request.
    fake = FakeOrchestrator(_happy_path_result())
    _override(fake)
    try:
        client = TestClient(app)
        response = client.post("/api/recommend", json={**VALID_REQUEST, "cuisine": "Indian", "cuisine_strict": True})
        assert response.status_code == 422
        assert not hasattr(fake, "request")
    finally:
        _clear()


def test_non_strict_unsupported_cuisine_is_still_accepted():
    # DEC-003: "indian"/"pakistani"/"desi" remain valid NON-strict
    # cuisine_preference values (they route to the separate
    # LocalCuratedRecipeProvider) -- this ticket only restricts STRICT
    # cuisine filtering, which is the combination that previously
    # produced silent, always-empty RecipeAPI.io results.
    fake = FakeOrchestrator(_happy_path_result())
    _override(fake)
    try:
        client = TestClient(app)
        response = client.post(
            "/api/recommend", json={**VALID_REQUEST, "cuisine": "Indian", "cuisine_strict": False}
        )
        assert response.status_code == 200
        assert fake.request.cuisine_preference == "Indian"
        assert fake.request.cuisine_strict is False
    finally:
        _clear()


def test_no_cuisine_search_still_works():
    _override(FakeOrchestrator(_happy_path_result()))
    try:
        client = TestClient(app)
        response = client.post("/api/recommend", json=VALID_REQUEST)
        assert response.status_code == 200
    finally:
        _clear()
