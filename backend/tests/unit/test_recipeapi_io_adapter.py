import httpx
import pytest

from app.config import Settings
from app.domain.errors import InvalidInputError
from app.domain.provider_errors import (
    RecipeNotFoundError,
    RecipeProviderConfigurationError,
    RecipeProviderMalformedResponseError,
    RecipeProviderRateLimitedError,
    RecipeProviderTimeoutError,
    RecipeProviderUnavailableError,
)
from app.integrations.recipeapi_io import RecipeAPIIOAdapter
from app.recipe.provider import SearchStrategy

# Obviously-fake fixture value, not a real credential. Used only to
# verify the adapter builds an Authorization header correctly and never
# leaks a key into errors/repr -- never the value from backend/.env.
FAKE_KEY = "test-only-fake-key-not-a-real-secret"


def make_settings(configured: bool = True) -> Settings:
    if configured:
        return Settings(_env_file=None, recipeapi_io_api_key=FAKE_KEY)
    return Settings(_env_file=None)


def make_adapter(handler, settings=None, **kwargs) -> RecipeAPIIOAdapter:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url=RecipeAPIIOAdapter.BASE_URL)
    return RecipeAPIIOAdapter(settings or make_settings(), http_client=client, **kwargs)


def json_response(status_code: int, payload: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload)

    return handler


DETAIL_PAYLOAD = {
    "data": {
        "id": 42,
        "name": "Chicken Biryani",
        "cuisine": "Indian",
        "meal_type": "main",
        "servings": 4,
        "prep_time": 20,
        "cook_time": 45,
        "instructions": ["Marinate chicken.", "Cook rice.", "Combine and dum cook."],
        "ingredients": [
            {"id": 1, "name": "chicken", "category": "meat", "quantity": 500, "unit": "g", "optional": False},
            {"id": 2, "name": "basmati rice", "category": "grain", "quantity": 2, "unit": "cup", "optional": False},
            {"id": 3, "name": "saffron", "category": "spice", "quantity": None, "unit": None, "optional": True},
        ],
    },
    "meta": {"language": "en"},
}


# --- constructor / configuration -------------------------------------------------


def test_constructor_raises_when_api_key_not_configured():
    with pytest.raises(RecipeProviderConfigurationError):
        RecipeAPIIOAdapter(make_settings(configured=False))


# --- reliability-invariant constructor validation (PP-002 review finding) -----------
#
# The adapter itself must enforce bounded retry / bounded timeout; a caller
# must not be able to bypass PP-002's reliability guarantees by overriding
# these constructor parameters with unbounded values.


def _client_with_call_counter():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, json={"data": [], "meta": {}})

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url=RecipeAPIIOAdapter.BASE_URL)
    return client, calls


def test_excessive_retry_count_is_rejected():
    client, calls = _client_with_call_counter()
    with pytest.raises(InvalidInputError):
        RecipeAPIIOAdapter(make_settings(), http_client=client, max_retries=1000)
    assert len(calls) == 0


def test_negative_retry_count_is_rejected():
    client, calls = _client_with_call_counter()
    with pytest.raises(InvalidInputError):
        RecipeAPIIOAdapter(make_settings(), http_client=client, max_retries=-1)
    assert len(calls) == 0


def test_zero_retries_is_permitted_at_construction():
    client, _ = _client_with_call_counter()
    adapter = RecipeAPIIOAdapter(make_settings(), http_client=client, max_retries=0)
    assert adapter._max_retries == 0


def test_one_retry_is_permitted_at_construction():
    client, _ = _client_with_call_counter()
    adapter = RecipeAPIIOAdapter(make_settings(), http_client=client, max_retries=1)
    assert adapter._max_retries == 1


def test_timeout_greater_than_five_seconds_is_rejected():
    client, calls = _client_with_call_counter()
    with pytest.raises(InvalidInputError):
        RecipeAPIIOAdapter(make_settings(), http_client=client, timeout_seconds=5.1)
    assert len(calls) == 0


def test_zero_timeout_is_rejected():
    client, calls = _client_with_call_counter()
    with pytest.raises(InvalidInputError):
        RecipeAPIIOAdapter(make_settings(), http_client=client, timeout_seconds=0)
    assert len(calls) == 0


def test_negative_timeout_is_rejected():
    client, calls = _client_with_call_counter()
    with pytest.raises(InvalidInputError):
        RecipeAPIIOAdapter(make_settings(), http_client=client, timeout_seconds=-1.0)
    assert len(calls) == 0


def test_timeout_up_to_five_seconds_is_permitted():
    client, _ = _client_with_call_counter()
    adapter = RecipeAPIIOAdapter(make_settings(), http_client=client, timeout_seconds=5.0)
    assert adapter._timeout_seconds == 5.0

    client2, _ = _client_with_call_counter()
    adapter2 = RecipeAPIIOAdapter(make_settings(), http_client=client2, timeout_seconds=3.0)
    assert adapter2._timeout_seconds == 3.0


def test_invalid_reliability_settings_never_issue_an_http_request():
    # Combined excessive retry + excessive timeout: construction must
    # fail before either constructor argument is used to build/issue a
    # request, and before the injected client is ever invoked.
    client, calls = _client_with_call_counter()
    with pytest.raises(InvalidInputError):
        RecipeAPIIOAdapter(make_settings(), http_client=client, max_retries=1000, timeout_seconds=60.0)
    assert len(calls) == 0


# --- successful mapping ------------------------------------------------------------


async def test_get_details_maps_full_recipe_with_provenance_and_timing():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/recipes/42"
        return httpx.Response(200, json=DETAIL_PAYLOAD)

    adapter = make_adapter(handler)
    recipe = await adapter.get_details("42")

    assert recipe.provider == "recipeapi_io"
    assert recipe.provider_recipe_id == "42"
    assert recipe.id == "recipeapi_io:42"
    assert recipe.name == "Chicken Biryani"
    assert recipe.cuisine == "Indian"
    assert recipe.category == "main"
    assert recipe.prep_time_minutes == 20
    assert recipe.cook_time_minutes == 45
    assert recipe.instructions == "Marinate chicken.\nCook rice.\nCombine and dum cook."

    assert len(recipe.ingredients) == 3
    chicken = recipe.ingredients[0]
    assert chicken.raw_name == "chicken"
    assert chicken.quantity == 500.0
    assert chicken.canonical_id is None  # canonical resolution deferred to M08, not this ticket
    assert chicken.normalization_status.value == "unknown"

    saffron = recipe.ingredients[2]
    assert saffron.optional is True
    assert saffron.quantity is None


async def test_missing_optional_fields_are_none_not_fabricated():
    payload = {"data": {"id": 1, "name": "Simple Toast", "instructions": "Toast bread."}}
    adapter = make_adapter(json_response(200, payload))
    recipe = await adapter.get_details("1")

    assert recipe.image_url is None
    assert recipe.source_url is None
    assert recipe.cuisine is None
    assert recipe.servings is None
    assert recipe.prep_time_minutes is None
    assert recipe.cook_time_minutes is None
    assert recipe.ingredients == []


async def test_provider_specific_raw_fields_do_not_leak_into_recipe():
    payload = {
        "data": {
            "id": 1,
            "name": "Test",
            "difficulty": "easy",
            "calories_per_serving": 300,
            "protein": 20,
            "dietary_tags": ["vegan"],
            "instructions": "Do it.",
        }
    }
    adapter = make_adapter(json_response(200, payload))
    recipe = await adapter.get_details("1")
    dumped = recipe.model_dump()
    # difficulty is now an intentional, first-class, typed Recipe field
    # (Module E) -- it is deliberately mapped, not leaked raw. Only the
    # remaining genuinely provider-specific fields must never appear.
    for leaked_field in ("calories_per_serving", "protein", "dietary_tags"):
        assert leaked_field not in dumped


@pytest.mark.parametrize(
    "raw_difficulty,expected",
    [
        ("easy", "easy"),
        ("Medium", "medium"),
        ("HARD", "hard"),
        ("expert", "unknown"),  # unrecognized value never guessed
        (None, "unknown"),
        (42, "unknown"),  # wrong type never guessed
    ],
)
async def test_difficulty_is_mapped_case_insensitively_with_unknown_fallback(raw_difficulty, expected):
    payload = {"data": {"id": 1, "name": "Test", "instructions": "Do it.", "difficulty": raw_difficulty}}
    adapter = make_adapter(json_response(200, payload))
    recipe = await adapter.get_details("1")
    assert recipe.difficulty.value == expected


async def test_missing_difficulty_field_entirely_is_unknown():
    payload = {"data": {"id": 1, "name": "Test", "instructions": "Do it."}}
    adapter = make_adapter(json_response(200, payload))
    recipe = await adapter.get_details("1")
    assert recipe.difficulty.value == "unknown"


# --- malformed responses ------------------------------------------------------------


async def test_malformed_detail_response_missing_data_raises():
    adapter = make_adapter(json_response(200, {"oops": True}))
    with pytest.raises(RecipeProviderMalformedResponseError):
        await adapter.get_details("1")


async def test_non_json_success_response_raises_malformed():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json")

    adapter = make_adapter(handler)
    with pytest.raises(RecipeProviderMalformedResponseError):
        await adapter.get_details("1")


async def test_detail_missing_usable_identity_raises():
    adapter = make_adapter(json_response(200, {"data": {"id": None, "name": "X"}}))
    with pytest.raises(RecipeProviderMalformedResponseError):
        await adapter.get_details("1")


async def test_search_response_missing_data_list_raises():
    adapter = make_adapter(json_response(200, {"meta": {}}))
    with pytest.raises(RecipeProviderMalformedResponseError):
        await adapter.search(SearchStrategy(query_ingredients=["rice"]))


# --- provider error mapping ----------------------------------------------------------


async def test_401_maps_to_configuration_error():
    adapter = make_adapter(json_response(401, {"error": {"code": "UNAUTHENTICATED", "message": "bad key"}}))
    with pytest.raises(RecipeProviderConfigurationError):
        await adapter.search(SearchStrategy(query_ingredients=["rice"]))


async def test_402_maps_to_configuration_error():
    adapter = make_adapter(
        json_response(402, {"error": {"code": "PLAN_FEATURE_UNAVAILABLE", "message": "upgrade plan"}})
    )
    with pytest.raises(RecipeProviderConfigurationError):
        await adapter.search(SearchStrategy(query_ingredients=["rice"]))


async def test_404_on_get_details_raises_recipe_not_found():
    adapter = make_adapter(json_response(404, {"error": {"code": "NOT_FOUND", "message": "no such recipe"}}))
    with pytest.raises(RecipeNotFoundError):
        await adapter.get_details("999")


async def test_422_raises_invalid_input_error():
    adapter = make_adapter(
        json_response(422, {"error": {"code": "UNSUPPORTED_LANGUAGE", "message": "bad lang"}})
    )
    with pytest.raises(InvalidInputError):
        await adapter.search(SearchStrategy(query_ingredients=["rice"]))


# --- reliability: timeout / retry / rate-limit / 5xx --------------------------------


async def test_timeout_retried_once_then_raises_typed_error():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        raise httpx.ReadTimeout("simulated timeout", request=request)

    adapter = make_adapter(handler, max_retries=1)
    with pytest.raises(RecipeProviderTimeoutError):
        await adapter.search(SearchStrategy(query_ingredients=["rice"]))
    assert len(calls) == 2  # initial attempt + exactly one bounded retry


async def test_rate_limit_is_not_retried():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(429, json={"error": {"code": "RATE_LIMIT", "message": "too many"}})

    adapter = make_adapter(handler, max_retries=1)
    with pytest.raises(RecipeProviderRateLimitedError):
        await adapter.search(SearchStrategy(query_ingredients=["rice"]))
    assert len(calls) == 1  # 429 must never be hammer-retried


async def test_server_error_retried_once_then_raises_unavailable():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503)

    adapter = make_adapter(handler, max_retries=1)
    with pytest.raises(RecipeProviderUnavailableError):
        await adapter.search(SearchStrategy(query_ingredients=["rice"]))
    assert len(calls) == 2


async def test_transport_error_retried_once_then_raises_unavailable():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        raise httpx.ConnectError("simulated connection failure", request=request)

    adapter = make_adapter(handler, max_retries=1)
    with pytest.raises(RecipeProviderUnavailableError):
        await adapter.search(SearchStrategy(query_ingredients=["rice"]))
    assert len(calls) == 2


async def test_timeout_then_retry_succeeds_returns_result():
    # Test-quality gap (audit finding, 2026-09-07): every existing retry
    # test only proved retries-exhausted-then-raise. This proves the
    # actual point of retrying -- a transient timeout followed by a
    # successful second attempt must return a valid result, not raise.
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ReadTimeout("simulated timeout", request=request)
        return httpx.Response(200, json={"data": [], "meta": {"current_page": 1, "last_page": 1}})

    adapter = make_adapter(handler, max_retries=1)
    result = await adapter.search(SearchStrategy(query_ingredients=["rice"]))
    assert result.items == []
    # initial failed attempt + one successful retry for the primary
    # query. Free-text enrichment is opt-in (enrich_free_text=False by
    # default, PR #15 correction pass, 2026-09-08) and was not
    # requested here, so no third call is made.
    assert len(calls) == 2


async def test_server_error_then_retry_succeeds_returns_result():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"data": [], "meta": {"current_page": 1, "last_page": 1}})

    adapter = make_adapter(handler, max_retries=1)
    result = await adapter.search(SearchStrategy(query_ingredients=["rice"]))
    assert result.items == []
    # See test_timeout_then_retry_succeeds_returns_result above.
    assert len(calls) == 2


async def test_zero_max_retries_means_single_attempt():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        raise httpx.ReadTimeout("simulated timeout", request=request)

    adapter = make_adapter(handler, max_retries=0)
    with pytest.raises(RecipeProviderTimeoutError):
        await adapter.search(SearchStrategy(query_ingredients=["rice"]))
    assert len(calls) == 1


# --- pagination / bounds ------------------------------------------------------------


async def test_per_page_never_exceeds_provider_free_plan_max():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["per_page"] = request.url.params.get("per_page")
        return httpx.Response(200, json={"data": [], "meta": {"current_page": 1, "last_page": 1}})

    adapter = make_adapter(handler)
    await adapter.search(SearchStrategy(page_size=10))
    assert captured["per_page"] == "10"


async def test_search_response_has_more_flag_from_pagination_meta():
    payload = {"data": [{"id": 1, "name": "A"}], "meta": {"current_page": 1, "last_page": 3}}
    adapter = make_adapter(json_response(200, payload))
    result = await adapter.search(SearchStrategy(query_ingredients=["x"]))
    assert result.has_more is True


async def test_search_response_has_more_false_on_last_page():
    payload = {"data": [{"id": 1, "name": "A"}], "meta": {"current_page": 3, "last_page": 3}}
    adapter = make_adapter(json_response(200, payload))
    result = await adapter.search(SearchStrategy(query_ingredients=["x"]))
    assert result.has_more is False


# --- duplicate identity / malformed item resilience ---------------------------------


async def test_search_dedupes_duplicate_recipe_ids_across_response():
    payload = {
        "data": [
            {"id": 1, "name": "Pasta A"},
            {"id": 1, "name": "Pasta A duplicate"},
            {"id": 2, "name": "Pasta B"},
        ],
        "meta": {"current_page": 1, "last_page": 1},
    }
    adapter = make_adapter(json_response(200, payload))
    result = await adapter.search(SearchStrategy(query_ingredients=["pasta"]))
    assert [item.provider_recipe_id for item in result.items] == ["1", "2"]


async def test_search_skips_malformed_items_without_failing_whole_page():
    payload = {
        "data": [
            {"id": 1, "name": "Good Recipe"},
            {"name": "Missing id"},
            {"id": 3, "name": ""},
        ],
        "meta": {"current_page": 1, "last_page": 1},
    }
    adapter = make_adapter(json_response(200, payload))
    result = await adapter.search(SearchStrategy(query_ingredients=["x"]))
    assert [item.provider_recipe_id for item in result.items] == ["1"]


# --- request construction ------------------------------------------------------------


async def test_search_query_params_include_ingredients_cuisine_and_max_prep_time():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"data": [], "meta": {}})

    adapter = make_adapter(handler)
    await adapter.search(
        SearchStrategy(query_ingredients=["rice", "chicken"], cuisine="Chinese", max_prep_time_minutes=30)
    )
    assert captured["params"]["ingredients"] == "rice,chicken"
    assert captured["params"]["cuisine"] == "chinese"
    assert captured["params"]["max_prep_time"] == "30"


async def test_search_lowercases_cuisine_for_provider_enum_compatibility():
    # Regression for a live-smoke-test finding (2026-09-05): the
    # provider's cuisine values are lowercase ("french", "american");
    # a capitalized filter value matched zero live results.
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["cuisine"] = request.url.params.get("cuisine")
        return httpx.Response(200, json={"data": [], "meta": {}})

    adapter = make_adapter(handler)
    await adapter.search(SearchStrategy(cuisine="  Italian  "))
    assert captured["cuisine"] == "italian"


# --- free-text search enrichment (retrieval fix 2026-09-08; made opt-in ------------
# in the PR #15 correction pass, same date)
#
# Live investigation (PR #15 browser review) found RecipeAPI.io's
# `ingredients` filter can silently contribute zero relevance signal for
# a real, well-represented ingredient term (confirmed for "chicken_wings":
# `ingredients=chicken_wings,garlic` returned a result set byte-identical
# to `ingredients=garlic` alone), while its `search` free-text field finds
# directly relevant recipes for the same concept. The merge behavior
# itself (interleave, dedupe, page_size cap, graceful degrade-on-failure)
# is unchanged; it now only runs when the caller sets
# SearchStrategy.enrich_free_text=True (Priority-1 efficiency fix: this
# used to double every non-empty-ingredients search's RecipeAPI.io
# request cost unconditionally).


async def test_search_enrichment_does_not_run_by_default():
    call_params = []

    def handler(request: httpx.Request) -> httpx.Response:
        call_params.append(dict(request.url.params))
        return httpx.Response(
            200,
            json={"data": [{"id": 1, "name": "Primary Match"}], "meta": {"current_page": 1, "last_page": 1}},
        )

    adapter = make_adapter(handler)
    result = await adapter.search(SearchStrategy(query_ingredients=["chicken_wings", "garlic"]))

    assert len(call_params) == 1
    assert [item.name for item in result.items] == ["Primary Match"]


async def test_search_merges_free_text_enrichment_results_when_requested():
    call_params = []

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        call_params.append(params)
        if "search" in params:
            return httpx.Response(
                200,
                json={"data": [{"id": 9, "name": "Enriched Match"}], "meta": {"current_page": 1, "last_page": 1}},
            )
        return httpx.Response(
            200,
            json={"data": [{"id": 1, "name": "Primary Match"}], "meta": {"current_page": 1, "last_page": 1}},
        )

    adapter = make_adapter(handler)
    result = await adapter.search(
        SearchStrategy(query_ingredients=["chicken_wings", "garlic"], enrich_free_text=True)
    )

    assert len(call_params) == 2
    assert call_params[0]["ingredients"] == "chicken_wings,garlic"
    assert "search" not in call_params[0]
    assert call_params[1]["ingredients"] == "chicken_wings,garlic"  # kept, not replaced
    assert call_params[1]["search"] == "chicken wings"  # primary anchor, humanized

    names = {item.name for item in result.items}
    assert names == {"Primary Match", "Enriched Match"}


async def test_search_enrichment_never_runs_without_query_ingredients_even_if_requested():
    call_params = []

    def handler(request: httpx.Request) -> httpx.Response:
        call_params.append(dict(request.url.params))
        return httpx.Response(200, json={"data": [], "meta": {"current_page": 1, "last_page": 1}})

    adapter = make_adapter(handler)
    await adapter.search(SearchStrategy(cuisine="Italian", enrich_free_text=True))

    assert len(call_params) == 1


async def test_search_enrichment_results_are_deduped_against_primary():
    def handler(request: httpx.Request) -> httpx.Response:
        # Both the primary and enriched calls return the exact same
        # recipe -- it must appear only once in the merged result.
        return httpx.Response(
            200, json={"data": [{"id": 1, "name": "Same Recipe"}], "meta": {"current_page": 1, "last_page": 1}}
        )

    adapter = make_adapter(handler)
    result = await adapter.search(SearchStrategy(query_ingredients=["onion"], enrich_free_text=True))

    assert [item.provider_recipe_id for item in result.items] == ["1"]


async def test_search_enrichment_survives_a_full_primary_page():
    # Regression for a real bug found during implementation: naively
    # concatenating primary-then-enriched before truncating to
    # page_size silently discarded every enriched item whenever the
    # primary query alone already filled a full page (the common case).
    # Interleaving must guarantee enriched items still get a slot.
    def handler(request: httpx.Request) -> httpx.Response:
        if "search" in dict(request.url.params):
            data = [{"id": 999, "name": "Enriched Only Match"}]
        else:
            # Primary already returns a full page on its own.
            data = [{"id": i, "name": f"Primary {i}"} for i in range(1, 11)]
        return httpx.Response(200, json={"data": data, "meta": {"current_page": 1, "last_page": 1}})

    adapter = make_adapter(handler)
    result = await adapter.search(
        SearchStrategy(query_ingredients=["chicken_wings"], page_size=10, enrich_free_text=True)
    )

    names = {item.name for item in result.items}
    assert "Enriched Only Match" in names
    assert len(result.items) == 10


async def test_search_enrichment_result_is_capped_at_page_size():
    def handler(request: httpx.Request) -> httpx.Response:
        if "search" in dict(request.url.params):
            data = [{"id": i, "name": f"Enriched {i}"} for i in range(100, 110)]
        else:
            data = [{"id": i, "name": f"Primary {i}"} for i in range(1, 11)]
        return httpx.Response(200, json={"data": data, "meta": {"current_page": 1, "last_page": 1}})

    adapter = make_adapter(handler)
    result = await adapter.search(SearchStrategy(query_ingredients=["onion"], page_size=10, enrich_free_text=True))

    assert len(result.items) == 10


async def test_search_enrichment_failure_never_fails_a_successful_primary_search():
    def handler(request: httpx.Request) -> httpx.Response:
        if "search" in dict(request.url.params):
            raise httpx.ConnectError("simulated enrichment failure", request=request)
        return httpx.Response(
            200, json={"data": [{"id": 1, "name": "Primary Match"}], "meta": {"current_page": 1, "last_page": 1}}
        )

    adapter = make_adapter(handler, max_retries=0)
    result = await adapter.search(SearchStrategy(query_ingredients=["onion"], enrich_free_text=True))

    assert [item.name for item in result.items] == ["Primary Match"]


async def test_search_enrichment_uses_only_the_primary_anchor_not_all_anchors():
    # Live-confirmed: joining every anchor into one `search` phrase
    # reliably returns zero results (the field behaves like a short
    # phrase match, not a bag-of-words match) -- only the first anchor
    # is ever used for the enrichment pass.
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        if "search" in params:
            captured["search"] = params["search"]
        return httpx.Response(200, json={"data": [], "meta": {"current_page": 1, "last_page": 1}})

    adapter = make_adapter(handler)
    await adapter.search(
        SearchStrategy(query_ingredients=["chicken_wings", "garlic", "ketchup"], enrich_free_text=True)
    )

    assert captured["search"] == "chicken wings"


# --- full recipe from list response, no separate detail fetch needed (Priority-1) ---
#
# Live investigation (2026-09-08) found RecipeAPI.io's /recipes
# (search/list) response items already carry the exact same
# ingredients/instructions/difficulty/servings/timing fields as a
# /recipes/{id} detail response, not a lightweight stub. When present,
# app.agent.tools.fetch_recipe_details uses this directly and skips the
# get_details() round trip for that candidate.

_FULL_LIST_ITEM = {
    "id": 42,
    "name": "Chicken Biryani",
    "cuisine": "Indian",
    "meal_type": "main",
    "difficulty": "medium",
    "servings": 4,
    "prep_time": 20,
    "cook_time": 45,
    "instructions": ["Marinate chicken.", "Cook rice."],
    "ingredients": [
        {"id": 1, "name": "chicken", "category": "meat", "quantity": 500, "unit": "g", "optional": False},
    ],
}


async def test_search_item_carries_full_recipe_when_list_response_is_complete():
    payload = {"data": [_FULL_LIST_ITEM], "meta": {"current_page": 1, "last_page": 1}}
    adapter = make_adapter(json_response(200, payload))
    result = await adapter.search(SearchStrategy(query_ingredients=["chicken"]))

    item = result.items[0]
    assert item.full_recipe is not None
    assert item.full_recipe.name == "Chicken Biryani"
    assert item.full_recipe.ingredients[0].raw_name == "chicken"
    assert item.full_recipe.instructions == "Marinate chicken.\nCook rice."


async def test_search_item_full_recipe_is_none_when_ingredients_missing():
    thin_item = {"id": 1, "name": "Thin Listing"}
    payload = {"data": [thin_item], "meta": {"current_page": 1, "last_page": 1}}
    adapter = make_adapter(json_response(200, payload))
    result = await adapter.search(SearchStrategy(query_ingredients=["chicken"]))

    assert result.items[0].full_recipe is None


async def test_search_item_full_recipe_is_none_when_instructions_missing():
    item = {**_FULL_LIST_ITEM, "instructions": []}
    payload = {"data": [item], "meta": {"current_page": 1, "last_page": 1}}
    adapter = make_adapter(json_response(200, payload))
    result = await adapter.search(SearchStrategy(query_ingredients=["chicken"]))

    assert result.items[0].full_recipe is None


async def test_search_item_full_recipe_skips_malformed_ingredient_entries_without_crashing():
    # A malformed nested ingredient entry (not a dict) must never crash
    # the whole search -- app._map_ingredient already skips it, exactly
    # as the existing get_details() path does; full_recipe is still
    # populated from whatever ingredients validly mapped.
    item = {**_FULL_LIST_ITEM, "ingredients": [_FULL_LIST_ITEM["ingredients"][0], "not-a-dict"]}
    payload = {"data": [item], "meta": {"current_page": 1, "last_page": 1}}
    adapter = make_adapter(json_response(200, payload))
    result = await adapter.search(SearchStrategy(query_ingredients=["chicken"]))

    assert result.items[0].full_recipe is not None
    assert len(result.items[0].full_recipe.ingredients) == 1


# --- secret non-leakage ---------------------------------------------------------------


async def test_authorization_header_uses_bearer_scheme():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"data": [], "meta": {}})

    adapter = make_adapter(handler)
    await adapter.search(SearchStrategy(query_ingredients=["rice"]))
    assert captured["auth"] == f"Bearer {FAKE_KEY}"


async def test_api_key_never_appears_in_raised_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"code": "UNAUTHENTICATED", "message": "bad key"}})

    adapter = make_adapter(handler)
    with pytest.raises(RecipeProviderConfigurationError) as excinfo:
        await adapter.search(SearchStrategy(query_ingredients=["rice"]))
    assert FAKE_KEY not in str(excinfo.value)
    assert FAKE_KEY not in repr(excinfo.value)


def test_adapter_repr_does_not_expose_api_key():
    # The adapter must keep the default object repr/str (no custom
    # __repr__/__str__ that would serialize internal state); the key is
    # still held internally to build the Authorization header, which is
    # expected -- the safety property is that it is never printed,
    # logged, or serialized, not that it is absent from memory.
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={}))
    client = httpx.AsyncClient(transport=transport)
    adapter = RecipeAPIIOAdapter(make_settings(), http_client=client)
    assert FAKE_KEY not in repr(adapter)
    assert FAKE_KEY not in str(adapter)


# --- client lifecycle -----------------------------------------------------------------


async def test_aclose_does_not_close_an_injected_client():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={}))
    injected_client = httpx.AsyncClient(transport=transport)
    adapter = RecipeAPIIOAdapter(make_settings(), http_client=injected_client)
    await adapter.aclose()
    assert injected_client.is_closed is False
    await injected_client.aclose()


# --- Blocker 2 / product decision: canonical identity vs provider-search -----
# wording (PR #15 fourth + fifth correction passes, 2026-09-08). The fifth
# pass removed specific-ingredient-to-broader-category broadening
# (basmati_rice/jasmine_rice/white_rice -> "rice") after live validation
# found it actively counterproductive -- it inflated result COUNT while
# destroying result RELEVANCE (the extra results were overwhelmingly a
# different rice form/preparation, not basmati rice). Only a true
# lexical/synonym rewording (minced_beef -> "ground beef", the SAME
# ingredient under a different common name) remains.


async def test_basmati_rice_provider_search_never_broadens_to_generic_rice():
    # Product decision (fifth correction pass): a SPECIFIC rice variety
    # must never broaden to the generic parent category "rice", even
    # when broadening is explicitly requested -- basmati_rice has no
    # entry in PROVIDER_SEARCH_TERM_OVERRIDES, so this is a no-op
    # regardless of the flag.
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["ingredients"] = request.url.params.get("ingredients")
        return httpx.Response(200, json={"data": [], "meta": {}})

    adapter = make_adapter(handler)
    await adapter.search(SearchStrategy(query_ingredients=["basmati_rice"], broaden_provider_search=True))
    assert captured["ingredients"] == "basmati_rice"


async def test_jasmine_rice_provider_search_never_broadens_to_generic_rice():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["ingredients"] = request.url.params.get("ingredients")
        return httpx.Response(200, json={"data": [], "meta": {}})

    adapter = make_adapter(handler)
    await adapter.search(SearchStrategy(query_ingredients=["jasmine_rice"], broaden_provider_search=True))
    assert captured["ingredients"] == "jasmine_rice"


async def test_white_rice_provider_search_never_broadens_to_generic_rice():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["ingredients"] = request.url.params.get("ingredients")
        return httpx.Response(200, json={"data": [], "meta": {}})

    adapter = make_adapter(handler)
    await adapter.search(SearchStrategy(query_ingredients=["white_rice"], broaden_provider_search=True))
    assert captured["ingredients"] == "white_rice"


async def test_lamb_cubes_provider_search_never_broadens_to_generic_lamb():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["ingredients"] = request.url.params.get("ingredients")
        return httpx.Response(200, json={"data": [], "meta": {}})

    adapter = make_adapter(handler)
    await adapter.search(SearchStrategy(query_ingredients=["lamb_cubes"], broaden_provider_search=True))
    assert captured["ingredients"] == "lamb_cubes"


async def test_chicken_wings_never_broadens_to_generic_chicken():
    # Blocker 2 safety rule: a specific animal cut must never broaden to
    # its generic parent, even when broadening is explicitly requested --
    # chicken_wings has no entry in PROVIDER_SEARCH_TERM_OVERRIDES, so
    # this is a no-op regardless of the flag.
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["ingredients"] = request.url.params.get("ingredients")
        return httpx.Response(200, json={"data": [], "meta": {}})

    adapter = make_adapter(handler)
    await adapter.search(SearchStrategy(query_ingredients=["chicken_wings"], broaden_provider_search=True))
    assert captured["ingredients"] == "chicken_wings"
    assert "chicken" != captured["ingredients"]


async def test_minced_beef_provider_search_broadens_to_ground_beef_lexical_synonym():
    # The one retained mapping: a true lexical/synonym rewording of the
    # exact same ingredient, not a category change.
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["ingredients"] = request.url.params.get("ingredients")
        return httpx.Response(200, json={"data": [], "meta": {}})

    adapter = make_adapter(handler)
    await adapter.search(SearchStrategy(query_ingredients=["minced_beef"], broaden_provider_search=True))
    assert captured["ingredients"] == "ground beef"


async def test_minced_beef_provider_search_stays_exact_when_broadening_not_requested():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["ingredients"] = request.url.params.get("ingredients")
        return httpx.Response(200, json={"data": [], "meta": {}})

    adapter = make_adapter(handler)
    await adapter.search(SearchStrategy(query_ingredients=["minced_beef"], broaden_provider_search=False))
    assert captured["ingredients"] == "minced_beef"


async def test_provider_search_broadening_only_affects_ids_with_a_reviewed_lexical_override():
    # A multi-anchor query broadens only the anchor with a reviewed
    # LEXICAL entry -- a specific-category id (basmati_rice) passes
    # through unchanged even when broadening is requested.
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["ingredients"] = request.url.params.get("ingredients")
        return httpx.Response(200, json={"data": [], "meta": {}})

    adapter = make_adapter(handler)
    await adapter.search(
        SearchStrategy(query_ingredients=["basmati_rice", "minced_beef"], broaden_provider_search=True)
    )
    assert captured["ingredients"] == "basmati_rice,ground beef"


async def test_provider_search_broadening_applies_to_free_text_enrichment_term_too():
    call_params = []

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        call_params.append(params)
        return httpx.Response(200, json={"data": [], "meta": {"current_page": 1, "last_page": 1}})

    adapter = make_adapter(handler)
    await adapter.search(
        SearchStrategy(query_ingredients=["minced_beef"], enrich_free_text=True, broaden_provider_search=True)
    )
    assert call_params[0]["ingredients"] == "ground beef"
    assert call_params[1]["search"] == "ground beef"


async def test_search_sends_every_canonical_supported_cuisine_unchanged():
    # 2026-09-13 cuisine-alignment fix (ticket section 5): the adapter
    # must send exactly SUPPORTED_STRICT_CUISINES' own lowercase values
    # to RecipeAPI.io -- never transformed into an unsupported variant.
    from app.recipe.provider import SUPPORTED_STRICT_CUISINES

    captured = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request.url.params.get("cuisine"))
        return httpx.Response(200, json={"data": [], "meta": {}})

    adapter = make_adapter(handler)
    for cuisine in sorted(SUPPORTED_STRICT_CUISINES):
        await adapter.search(SearchStrategy(cuisine=cuisine))

    assert captured == sorted(SUPPORTED_STRICT_CUISINES)


# -- GET /ingredients?search= catalogue (2026-09-13 unified ingredient -----
# resolution ticket, section 8) ---------------------------------------------


async def test_search_ingredients_maps_the_real_confirmed_live_response_shape():
    payload = {
        "data": [
            {"id": 1139, "name": "Lamb chop", "category": "meat"},
            {"id": 3767, "name": "Lamb belly", "category": "meat"},
        ],
        "links": {},
        "meta": {"total": 2},
    }
    adapter = make_adapter(json_response(200, payload))
    results = await adapter.search_ingredients("lamb")
    assert [(r.provider_id, r.name, r.category) for r in results] == [
        ("1139", "Lamb chop", "meat"),
        ("3767", "Lamb belly", "meat"),
    ]


async def test_search_ingredients_sends_the_search_query_param():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"data": []})

    adapter = make_adapter(handler)
    await adapter.search_ingredients("lamb chop")
    assert captured["params"] == {"search": "lamb chop"}


async def test_search_ingredients_empty_query_returns_empty_without_a_request():
    called = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        called["count"] += 1
        return httpx.Response(200, json={"data": []})

    adapter = make_adapter(handler)
    assert await adapter.search_ingredients("   ") == []
    assert called["count"] == 0


async def test_search_ingredients_skips_malformed_individual_items():
    payload = {"data": [{"id": 1, "name": "Chicken"}, {"id": None, "name": "Bad"}, {"name": "Also bad"}, "not a dict"]}
    adapter = make_adapter(json_response(200, payload))
    results = await adapter.search_ingredients("chicken")
    assert [r.name for r in results] == ["Chicken"]


async def test_search_ingredients_raises_on_malformed_top_level_response():
    adapter = make_adapter(json_response(200, {"no_data_key": True}))
    with pytest.raises(RecipeProviderMalformedResponseError):
        await adapter.search_ingredients("chicken")
