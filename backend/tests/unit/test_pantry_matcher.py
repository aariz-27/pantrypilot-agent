from app.domain.models import NormalizationStatus, RecipeIngredient
from app.domain.pantry_matcher import match_pantry


def ingredient(raw, canonical, optional=False):
    return RecipeIngredient(
        raw_name=raw,
        canonical_id=canonical,
        normalization_status=NormalizationStatus.EXACT if canonical else NormalizationStatus.UNKNOWN,
        optional=optional,
    )


def test_spec_example_four_matched_one_missing_point_eight_coverage():
    pantry = frozenset({"chicken_breast", "rice", "onion", "garlic"})
    recipe_ingredients = [
        ingredient("chicken breast", "chicken_breast"),
        ingredient("rice", "rice"),
        ingredient("onion", "onion"),
        ingredient("garlic", "garlic"),
        ingredient("soy sauce", "soy_sauce"),
    ]
    result = match_pantry(pantry, recipe_ingredients)
    assert result.matched_ingredients == ("chicken_breast", "garlic", "onion", "rice")
    assert result.missing_ingredients == ("soy_sauce",)
    assert result.missing_count == 1
    assert result.pantry_coverage == 0.8


def test_full_match_zero_missing():
    pantry = frozenset({"egg", "bread", "cheese"})
    recipe_ingredients = [ingredient("egg", "egg"), ingredient("bread", "bread"), ingredient("cheese", "cheese")]
    result = match_pantry(pantry, recipe_ingredients)
    assert result.missing_count == 0
    assert result.pantry_coverage == 1.0


def test_empty_pantry():
    pantry = frozenset()
    recipe_ingredients = [ingredient("rice", "rice")]
    result = match_pantry(pantry, recipe_ingredients)
    assert result.pantry_coverage == 0.0
    assert result.missing_ingredients == ("rice",)


def test_duplicate_recipe_lines_count_once():
    pantry = frozenset({"onion"})
    recipe_ingredients = [
        ingredient("onion", "onion"),
        ingredient("onions", "onion"),
        ingredient("red onion", "onion"),
    ]
    result = match_pantry(pantry, recipe_ingredients)
    assert result.matched_ingredients == ("onion",)
    assert result.missing_count == 0
    assert result.pantry_coverage == 1.0


def test_unknown_required_ingredient_never_counts_as_match_but_reduces_coverage():
    # Regression for defect: an UNKNOWN required ingredient must never be
    # assumed matched, must never be fabricated a canonical ID, must stay
    # visible in unresolved_ingredients, must never appear in the
    # canonical-only missing_ingredients list, and must reduce coverage
    # (TECHNICAL_SPEC.md section 11).
    pantry = frozenset({"rice"})
    recipe_ingredients = [
        ingredient("rice", "rice"),
        ingredient("dried lotus root shavings", None),
    ]
    result = match_pantry(pantry, recipe_ingredients)
    assert result.pantry_coverage == 0.5
    assert result.unresolved_ingredients == ("dried lotus root shavings",)
    assert "dried lotus root shavings" not in result.missing_ingredients
    assert "dried lotus root shavings" not in result.matched_ingredients


def test_resolved_plus_unresolved_required_ingredient_reduces_coverage_below_one():
    pantry = frozenset({"rice"})
    recipe_ingredients = [
        ingredient("rice", "rice"),
        ingredient("some unmapped exotic spice", None),
    ]
    result = match_pantry(pantry, recipe_ingredients)
    assert result.pantry_coverage < 1.0
    assert result.pantry_coverage == 0.5


def test_only_required_ingredient_unresolved_is_not_full_coverage():
    pantry = frozenset({"rice"})
    recipe_ingredients = [ingredient("some unmapped exotic spice", None)]
    result = match_pantry(pantry, recipe_ingredients)
    assert result.pantry_coverage != 1.0
    assert result.pantry_coverage == 0.0
    assert result.unresolved_ingredients == ("some unmapped exotic spice",)


def test_optional_unresolved_ingredient_excluded_from_denominator():
    pantry = frozenset({"rice"})
    recipe_ingredients = [
        ingredient("rice", "rice"),
        ingredient("some unmapped exotic spice", None, optional=True),
    ]
    result = match_pantry(pantry, recipe_ingredients)
    # The optional unresolved ingredient must not reduce coverage, but it
    # must remain visible for display.
    assert result.pantry_coverage == 1.0
    assert result.unresolved_ingredients == ("some unmapped exotic spice",)


def test_duplicate_unresolved_required_ingredients_count_once_in_denominator():
    pantry = frozenset({"rice"})
    recipe_ingredients = [
        ingredient("rice", "rice"),
        ingredient("Some Unmapped Spice", None),
        ingredient("some unmapped spice", None),  # same item, different casing/whitespace
    ]
    result = match_pantry(pantry, recipe_ingredients)
    # If the duplicate were not deduplicated, coverage would be 1/3.
    assert result.pantry_coverage == 0.5


def test_optional_ingredient_excluded_from_denominator():
    pantry = frozenset({"rice"})
    recipe_ingredients = [
        ingredient("rice", "rice"),
        ingredient("coriander", "coriander", optional=True),
    ]
    result = match_pantry(pantry, recipe_ingredients)
    assert result.pantry_coverage == 1.0
    assert "coriander" not in result.missing_ingredients


def test_no_required_ingredients_is_full_coverage_by_convention():
    pantry = frozenset()
    recipe_ingredients = [ingredient("coriander", "coriander", optional=True)]
    result = match_pantry(pantry, recipe_ingredients)
    assert result.pantry_coverage == 1.0
    assert result.missing_count == 0


def test_non_food_other_requirement_excluded_from_coverage():
    pantry = frozenset({"chicken_breast"})
    recipe_ingredients = [
        ingredient("chicken breast", "chicken_breast"),
        ingredient("kitchen twine", "kitchen_twine"),
    ]
    result = match_pantry(pantry, recipe_ingredients)
    assert result.pantry_coverage == 1.0
    assert result.other_requirements == ("kitchen_twine",)
    assert "kitchen_twine" not in result.missing_ingredients
