import pytest

from app.domain.provider_errors import RecipeProviderMalformedResponseError
from app.recipe.mapping import build_recipe_id, require_usable_identity


def test_build_recipe_id_format():
    assert build_recipe_id("recipeapi_io", "123") == "recipeapi_io:123"


def test_require_usable_identity_passes_with_valid_fields():
    recipe_id, name = require_usable_identity(
        provider="recipeapi_io", provider_recipe_id=42, name="  Test Recipe  ", source_description="test"
    )
    assert recipe_id == "42"
    assert name == "Test Recipe"


@pytest.mark.parametrize(
    "provider_recipe_id,name",
    [
        (None, "Has a name"),
        ("", "Has a name"),
        ("  ", "Has a name"),
        (123, None),
        (123, ""),
        (123, "   "),
        (None, None),
    ],
)
def test_require_usable_identity_rejects_missing_fields(provider_recipe_id, name):
    with pytest.raises(RecipeProviderMalformedResponseError):
        require_usable_identity(
            provider="recipeapi_io",
            provider_recipe_id=provider_recipe_id,
            name=name,
            source_description="test",
        )
