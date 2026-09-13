"""Safe provider-name matching tiers (ticket section 16) -- pure,
I/O-free domain logic. See app.domain.ingredient_resolution's module
docstring for the A-E identity separation this protects.
"""

from __future__ import annotations

from app.domain.ingredient_resolution import (
    IngredientResolutionState,
    ProviderIngredient,
    humanize_for_provider,
    select_safe_provider_match,
    singular_plural_query_variants,
)


def _pi(name: str, provider_id: str = "1", category: str | None = "meat") -> ProviderIngredient:
    return ProviderIngredient(provider_id=provider_id, name=name, category=category)


def test_humanize_replaces_underscores_and_hyphens_with_spaces():
    assert humanize_for_provider("lamb_chops") == "lamb chops"
    assert humanize_for_provider("stir-fry_sauce") == "stir fry sauce"


def test_exact_case_insensitive_match_resolves():
    match, state = select_safe_provider_match("chicken", [_pi("Chicken", "125", "poultry")])
    assert match is not None
    assert match.provider_id == "125"
    assert state == IngredientResolutionState.PROVIDER_CATALOG_RESOLVED


def test_singular_plural_variant_resolves_the_confirmed_live_lamb_chops_gap():
    # Live-confirmed (2026-09-13): RecipeAPI.io's own catalogue lists
    # "Lamb chop" (singular); PantryPilot's canonical id is plural
    # ("lamb_chops" -> humanized "lamb chops"). This is the actual
    # production bug this ticket fixes.
    match, state = select_safe_provider_match(
        "lamb chops", [_pi("Lamb chop", "1139"), _pi("Lamb broth", "1146", "other")]
    )
    assert match is not None
    assert match.name == "Lamb chop"
    assert state == IngredientResolutionState.PROVIDER_CATALOG_RESOLVED


def test_never_matches_a_semantically_different_ingredient():
    # Ticket section 16's own explicit counter-example: "lamb chops"
    # must never resolve to "Lamb liver" merely because both start with
    # "lamb" -- neither exact nor singular/plural tiers ever accept a
    # substring/fuzzy match.
    match, state = select_safe_provider_match("lamb chops", [_pi("Lamb liver", "3111")])
    assert match is None
    assert state == IngredientResolutionState.UNRESOLVED


def test_never_matches_chicken_to_chicken_broth_on_text_overlap_alone():
    match, state = select_safe_provider_match("chicken", [_pi("Chicken broth", "257", "other")])
    assert match is None
    assert state == IngredientResolutionState.UNRESOLVED


def test_no_candidates_is_unresolved_not_ambiguous():
    match, state = select_safe_provider_match("chicken", [])
    assert match is None
    assert state == IngredientResolutionState.UNRESOLVED


def test_empty_query_is_unresolved():
    match, state = select_safe_provider_match("   ", [_pi("Chicken")])
    assert match is None
    assert state == IngredientResolutionState.UNRESOLVED


def test_multiple_exact_matches_is_ambiguous_never_silently_narrowed():
    # Ticket section 11: "chik" must not silently become one specific
    # chicken cut. A catalogue returning more than one candidate that
    # clears the SAME best tier is reported as AMBIGUOUS, never resolved
    # to "the first one".
    match, state = select_safe_provider_match(
        "chik", [_pi("chik", "1", "poultry"), _pi("Chik", "2", "poultry")]
    )
    assert match is None
    assert state == IngredientResolutionState.AMBIGUOUS


def test_multiple_variant_matches_is_ambiguous():
    # Neither candidate is an EXACT match for "chicken wing" (both are
    # the plural variant, spelled two different ways) -- two distinct
    # provider entries tie at the variant tier, so this must be
    # AMBIGUOUS rather than silently picking the first one.
    match, state = select_safe_provider_match(
        "chicken wing", [_pi("Chicken Wings", "1"), _pi("chicken-wings", "2")]
    )
    assert match is None
    assert state == IngredientResolutionState.AMBIGUOUS


def test_hyphen_and_underscore_normalized_equivalently_to_spaces():
    match, state = select_safe_provider_match("stir-fry sauce", [_pi("stir_fry sauce", "1")])
    assert match is not None
    assert state == IngredientResolutionState.PROVIDER_CATALOG_RESOLVED


def test_singular_plural_query_variants_strips_a_trailing_s():
    assert singular_plural_query_variants("lamb chops") == ["lamb chop"]


def test_singular_plural_query_variants_adds_a_trailing_s_for_a_singular_word():
    assert singular_plural_query_variants("mutton") == ["muttons"]


def test_singular_plural_query_variants_excludes_the_original_text():
    assert "lamb chops" not in singular_plural_query_variants("lamb chops")


def test_singular_plural_query_variants_of_empty_text_is_empty():
    assert singular_plural_query_variants("") == []
