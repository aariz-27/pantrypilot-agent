"""Module E: deterministic serving-count scaling.

Scales a grounded recipe's ingredient quantities from the provider's
own original serving count to the user's requested serving count, so
downstream cost estimation (app.domain.cost_engine) reflects the
quantity the user will actually need to buy.

Hard rules (ticket section 9):
- use the provider's original serving count where available; never
  invent one when it is missing;
- scaling factor = requested_servings / provider_servings;
- only reliably-parseable ingredient lines (app.domain.grocery_parsing.
  parse_package_content already normalizes these into g/ml/pcs) are
  scaled -- an ambiguous/unsupported measure is left exactly as the
  provider supplied it, never guessed;
- prep_time_minutes/cook_time_minutes are never touched here;
- this module never calls the LLM and is not itself a source of new
  canonical IDs or units -- it only multiplies an already-normalized
  quantity by a plain scalar.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.grocery_parsing import parse_package_content
from app.domain.models import Recipe, RecipeIngredient


@dataclass(frozen=True)
class ScaledRecipe:
    recipe: Recipe
    requested_servings: int
    original_servings: int | None
    scaling_applied: bool
    scaling_factor: float | None


def _scale_ingredient(ingredient: RecipeIngredient, factor: float) -> RecipeIngredient:
    parsed = parse_package_content(ingredient.raw_measure)
    if parsed.normalized_total_quantity is None or parsed.normalized_unit is None:
        # Ambiguous/unsupported/unparseable measure ("a pinch", "to
        # taste", "2 x 1 kg" additive packs, etc.) -- preserve the
        # grounded provider text exactly rather than fabricating a
        # scaled number for it.
        return ingredient

    scaled_quantity = round(parsed.normalized_total_quantity * factor, 4)
    return ingredient.model_copy(
        update={
            "quantity": scaled_quantity,
            "raw_measure": f"{scaled_quantity} {parsed.normalized_unit}",
        }
    )


def scale_recipe_servings(recipe: Recipe, requested_servings: int) -> ScaledRecipe:
    """Returns a ScaledRecipe wrapping a recipe whose reliably-parseable
    ingredient quantities have been scaled to `requested_servings`.

    No-op (scaling_applied=False) when the provider's original serving
    count is unavailable or not a usable positive integer -- the
    original grounded recipe is returned unchanged rather than assuming
    a serving count PantryPilot was never told.
    """

    original_servings = recipe.servings
    if original_servings is None or original_servings <= 0 or requested_servings <= 0:
        return ScaledRecipe(
            recipe=recipe,
            requested_servings=requested_servings,
            original_servings=original_servings,
            scaling_applied=False,
            scaling_factor=None,
        )

    factor = requested_servings / original_servings
    if factor == 1.0:
        # Requested servings already match the provider's original
        # count -- nothing to scale, but this is still a fully known,
        # confident 1:1 relationship (not "unavailable").
        return ScaledRecipe(
            recipe=recipe,
            requested_servings=requested_servings,
            original_servings=original_servings,
            scaling_applied=True,
            scaling_factor=1.0,
        )

    scaled_ingredients = [_scale_ingredient(ing, factor) for ing in recipe.ingredients]
    scaled_recipe = recipe.model_copy(update={"ingredients": scaled_ingredients})
    return ScaledRecipe(
        recipe=scaled_recipe,
        requested_servings=requested_servings,
        original_servings=original_servings,
        scaling_applied=True,
        scaling_factor=factor,
    )
