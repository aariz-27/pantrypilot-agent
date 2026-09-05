import pytest

from app.domain.provider_errors import RecipeNotFoundError
from app.integrations.local_curated import (
    CuratedIngredientInput,
    CuratedRecordInput,
    LocalCuratedRecipeProvider,
)
from app.recipe.provider import SearchStrategy

# Clearly-marked test fixture data, not production curated content
# (DEC-012 remains open; the final curated dataset is a separate,
# explicitly authorized ticket).
TEST_FIXTURE_RECORDS = [
    CuratedRecordInput(
        recipe_id="test-biryani-1",
        name="Test Chicken Biryani",
        cuisine="Pakistani",
        source_label="Test fixture (not production content)",
        provenance_note="Manually authored for PP-002 automated tests only.",
        ingredients=[
            CuratedIngredientInput(raw_name="chicken", quantity=500, unit="g", canonical_id="chicken_breast"),
            CuratedIngredientInput(raw_name="basmati rice", quantity=2, unit="cup"),
            CuratedIngredientInput(raw_name="saffron", optional=True),
        ],
        instructions="Marinate, layer, dum cook.",
        servings=4,
        prep_time_minutes=20,
        cook_time_minutes=45,
    ),
    CuratedRecordInput(
        recipe_id="test-nihari-1",
        name="Test Nihari",
        cuisine="Pakistani",
        source_label="Test fixture (not production content)",
        provenance_note="Manually authored for PP-002 automated tests only.",
        ingredients=[CuratedIngredientInput(raw_name="beef shank", quantity=1, unit="kg")],
        instructions="Slow cook overnight.",
    ),
    CuratedRecordInput(
        recipe_id="test-inactive-1",
        name="Test Withdrawn Recipe",
        cuisine="Indian",
        source_label="Test fixture (not production content)",
        provenance_note="Manually authored for PP-002 automated tests only.",
        is_active=False,
    ),
]


def make_provider() -> LocalCuratedRecipeProvider:
    return LocalCuratedRecipeProvider(list(TEST_FIXTURE_RECORDS))


# --- provenance ------------------------------------------------------------


async def test_get_details_preserves_local_provenance():
    provider = make_provider()
    recipe = await provider.get_details("test-biryani-1")
    assert recipe.provider == "local_curated"
    assert recipe.provider_recipe_id == "test-biryani-1"
    assert recipe.id == "local_curated:test-biryani-1"
    assert recipe.source_label == "Test fixture (not production content)"
    assert recipe.provenance_note == "Manually authored for PP-002 automated tests only."


def test_curated_record_requires_mandatory_provenance():
    with pytest.raises(ValueError):
        CuratedRecordInput(
            recipe_id="bad",
            name="Bad Record",
            cuisine="Indian",
            source_label="   ",
            provenance_note="something",
        )


# --- read-only contract ------------------------------------------------------------


def test_provider_exposes_no_write_methods():
    provider = make_provider()
    for forbidden in ("create", "update", "delete", "add_recipe", "remove_recipe"):
        assert not hasattr(provider, forbidden)


def test_duplicate_recipe_id_fails_visibly_rather_than_silently_coexisting():
    duplicate = CuratedRecordInput(
        recipe_id="test-biryani-1",
        name="Duplicate",
        cuisine="Pakistani",
        source_label="Test fixture",
        provenance_note="Test fixture",
    )
    with pytest.raises(ValueError):
        LocalCuratedRecipeProvider([TEST_FIXTURE_RECORDS[0], duplicate])


async def test_inactive_record_is_not_returned():
    provider = make_provider()
    with pytest.raises(RecipeNotFoundError):
        await provider.get_details("test-inactive-1")

    result = await provider.search(SearchStrategy(cuisine="Indian"))
    assert result.items == []


# --- search / routing ------------------------------------------------------------


async def test_search_filters_by_cuisine():
    provider = make_provider()
    result = await provider.search(SearchStrategy(cuisine="Pakistani"))
    ids = {item.provider_recipe_id for item in result.items}
    assert ids == {"test-biryani-1", "test-nihari-1"}


async def test_search_filters_by_ingredient():
    provider = make_provider()
    result = await provider.search(SearchStrategy(query_ingredients=["beef shank"]))
    assert [item.provider_recipe_id for item in result.items] == ["test-nihari-1"]


async def test_search_with_no_filters_returns_all_active():
    provider = make_provider()
    result = await provider.search(SearchStrategy())
    assert len(result.items) == 2


async def test_search_strict_cuisine_with_no_match_returns_empty_not_substitute():
    provider = make_provider()
    result = await provider.search(SearchStrategy(cuisine="Thai"))
    assert result.items == []


# --- mapping fidelity ------------------------------------------------------------


async def test_get_details_maps_ingredients_and_timing_without_fabrication():
    provider = make_provider()
    recipe = await provider.get_details("test-biryani-1")

    assert recipe.prep_time_minutes == 20
    assert recipe.cook_time_minutes == 45
    assert len(recipe.ingredients) == 3

    chicken = recipe.ingredients[0]
    assert chicken.canonical_id == "chicken_breast"  # curator-supplied, not fabricated by this code
    saffron = recipe.ingredients[2]
    assert saffron.optional is True
    assert saffron.canonical_id is None  # never fabricated when curator didn't supply one


async def test_get_details_unknown_id_raises_not_found():
    provider = make_provider()
    with pytest.raises(RecipeNotFoundError):
        await provider.get_details("does-not-exist")
