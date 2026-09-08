from app.domain.models import Recipe, RecipeIngredient
from app.domain.serving_scaler import scale_recipe_servings


def make_recipe(servings, ingredients):
    return Recipe(
        id="recipeapi_io:1",
        provider="recipeapi_io",
        provider_recipe_id="1",
        name="Test Recipe",
        servings=servings,
        ingredients=ingredients,
    )


def test_doubling_servings_doubles_reliable_quantities():
    recipe = make_recipe(2, [RecipeIngredient(raw_name="rice", raw_measure="500 g", quantity=500)])
    result = scale_recipe_servings(recipe, requested_servings=4)

    assert result.scaling_applied is True
    assert result.scaling_factor == 2.0
    assert result.original_servings == 2
    scaled_ing = result.recipe.ingredients[0]
    assert scaled_ing.raw_measure == "1000.0 g"
    assert scaled_ing.quantity == 1000.0


def test_halving_servings_halves_reliable_quantities():
    recipe = make_recipe(4, [RecipeIngredient(raw_name="onion", raw_measure="200 g", quantity=200)])
    result = scale_recipe_servings(recipe, requested_servings=2)

    assert result.scaling_factor == 0.5
    assert result.recipe.ingredients[0].raw_measure == "100.0 g"


def test_requested_servings_equal_to_original_is_noop_but_marked_applied():
    recipe = make_recipe(4, [RecipeIngredient(raw_name="onion", raw_measure="200 g", quantity=200)])
    result = scale_recipe_servings(recipe, requested_servings=4)

    assert result.scaling_applied is True
    assert result.scaling_factor == 1.0
    assert result.recipe.ingredients[0].raw_measure == "200 g"  # untouched, not re-formatted


def test_missing_original_servings_is_not_scaled_and_preserves_grounded_data():
    recipe = make_recipe(None, [RecipeIngredient(raw_name="rice", raw_measure="500 g", quantity=500)])
    result = scale_recipe_servings(recipe, requested_servings=4)

    assert result.scaling_applied is False
    assert result.scaling_factor is None
    assert result.recipe is recipe  # exact original object, nothing fabricated
    assert result.recipe.ingredients[0].raw_measure == "500 g"


def test_zero_or_negative_original_servings_is_not_scaled():
    recipe = make_recipe(0, [RecipeIngredient(raw_name="rice", raw_measure="500 g", quantity=500)])
    result = scale_recipe_servings(recipe, requested_servings=4)
    assert result.scaling_applied is False


def test_ambiguous_measure_is_preserved_exactly_never_guessed():
    recipe = make_recipe(2, [RecipeIngredient(raw_name="salt", raw_measure="a pinch", quantity=None)])
    result = scale_recipe_servings(recipe, requested_servings=4)

    assert result.scaling_applied is True
    scaled_ing = result.recipe.ingredients[0]
    assert scaled_ing.raw_measure == "a pinch"
    assert scaled_ing.quantity is None


def test_mixed_reliable_and_ambiguous_lines_only_scales_the_reliable_one():
    recipe = make_recipe(
        2,
        [
            RecipeIngredient(raw_name="rice", raw_measure="500 g", quantity=500),
            RecipeIngredient(raw_name="salt", raw_measure="to taste", quantity=None),
        ],
    )
    result = scale_recipe_servings(recipe, requested_servings=6)

    assert result.recipe.ingredients[0].raw_measure == "1500.0 g"
    assert result.recipe.ingredients[1].raw_measure == "to taste"


def test_prep_and_cook_time_are_never_scaled():
    recipe = Recipe(
        id="recipeapi_io:1",
        provider="recipeapi_io",
        provider_recipe_id="1",
        name="Test Recipe",
        servings=2,
        prep_time_minutes=10,
        cook_time_minutes=20,
        ingredients=[RecipeIngredient(raw_name="rice", raw_measure="500 g", quantity=500)],
    )
    result = scale_recipe_servings(recipe, requested_servings=8)
    assert result.recipe.prep_time_minutes == 10
    assert result.recipe.cook_time_minutes == 20


def test_never_invents_an_original_serving_count_from_requested_servings_alone():
    recipe = make_recipe(None, [])
    result = scale_recipe_servings(recipe, requested_servings=4)
    assert result.original_servings is None
    assert result.scaling_applied is False
