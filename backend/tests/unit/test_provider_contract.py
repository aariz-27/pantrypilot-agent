"""Provider contract tests (TECHNICAL_SPEC.md section 22): RecipeAPI.io
and LocalCuratedRecipeProvider must return an equivalent internal
Recipe DTO shape, both implementing the same RecipeProvider contract."""

import httpx
import pytest

from app.config import Settings
from app.domain.models import Recipe
from app.integrations.local_curated import (
    CuratedIngredientInput,
    CuratedRecordInput,
    LocalCuratedRecipeProvider,
)
from app.integrations.recipeapi_io import RecipeAPIIOAdapter
from app.recipe.provider import RecipeProvider, SearchStrategy


def _recipeapi_provider() -> RecipeAPIIOAdapter:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/recipes"):
            return httpx.Response(
                200,
                json={"data": [{"id": 1, "name": "Contract Test Recipe"}], "meta": {"current_page": 1, "last_page": 1}},
            )
        return httpx.Response(
            200,
            json={"data": {"id": 1, "name": "Contract Test Recipe", "instructions": "Cook it."}},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url=RecipeAPIIOAdapter.BASE_URL)
    settings = Settings(_env_file=None, recipeapi_io_api_key="test-only-fake-key-not-a-real-secret")
    return RecipeAPIIOAdapter(settings, http_client=client)


def _local_curated_provider() -> LocalCuratedRecipeProvider:
    return LocalCuratedRecipeProvider(
        [
            CuratedRecordInput(
                recipe_id="1",
                name="Contract Test Recipe",
                cuisine="Pakistani",
                source_label="Test fixture (not production content)",
                provenance_note="Test fixture only.",
                ingredients=[CuratedIngredientInput(raw_name="salt")],
                instructions="Cook it.",
            )
        ]
    )


@pytest.fixture(params=["recipeapi_io", "local_curated"])
def provider(request) -> RecipeProvider:
    if request.param == "recipeapi_io":
        return _recipeapi_provider()
    return _local_curated_provider()


async def test_search_returns_provider_neutral_result(provider: RecipeProvider):
    result = await provider.search(SearchStrategy())
    assert len(result.items) == 1
    item = result.items[0]
    assert item.provider == provider.provider_name
    assert item.provider_recipe_id == "1"
    assert item.id == f"{provider.provider_name}:1"
    assert item.name == "Contract Test Recipe"


async def test_get_details_returns_recipe_dto(provider: RecipeProvider):
    recipe = await provider.get_details("1")
    assert isinstance(recipe, Recipe)
    assert recipe.provider == provider.provider_name
    assert recipe.provider_recipe_id == "1"
    assert recipe.id == f"{provider.provider_name}:1"
    assert recipe.name == "Contract Test Recipe"
    assert recipe.instructions == "Cook it."
