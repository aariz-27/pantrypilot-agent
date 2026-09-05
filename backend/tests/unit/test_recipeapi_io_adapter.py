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
    for leaked_field in ("difficulty", "calories_per_serving", "protein", "dietary_tags"):
        assert leaked_field not in dumped


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
