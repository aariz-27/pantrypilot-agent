from app.domain.ingredient_normalizer import normalize_ingredient_name, normalize_pantry
from app.domain.models import NormalizationStatus


def test_exact_match():
    result = normalize_ingredient_name("rice")
    assert result.canonical_id == "rice"
    assert result.status == NormalizationStatus.EXACT


def test_case_and_whitespace_insensitive():
    result = normalize_ingredient_name("  RICE  ")
    assert result.canonical_id == "rice"
    assert result.status == NormalizationStatus.EXACT


def test_punctuation_cleanup():
    result = normalize_ingredient_name("garlic!!")
    assert result.canonical_id == "garlic"


def test_plural_normalization_via_naive_suffix_stripping():
    result = normalize_ingredient_name("carrots")
    assert result.canonical_id == "carrot"
    assert result.status == NormalizationStatus.EXACT


def test_alias_synonym_capsicum():
    result = normalize_ingredient_name("Capsicum")
    assert result.canonical_id == "bell_pepper"
    assert result.status == NormalizationStatus.ALIAS


def test_alias_marketing_term_chicken_breast():
    result = normalize_ingredient_name("Boneless Chicken Breast")
    assert result.canonical_id == "chicken_breast"
    assert result.status == NormalizationStatus.ALIAS


def test_alias_plural_onions():
    result = normalize_ingredient_name("onions")
    assert result.canonical_id == "onion"


def test_unknown_specialty_item():
    result = normalize_ingredient_name("dried lotus root shavings")
    assert result.canonical_id is None
    assert result.status == NormalizationStatus.UNKNOWN


def test_empty_string_is_unknown_not_an_error():
    result = normalize_ingredient_name("")
    assert result.canonical_id is None
    assert result.status == NormalizationStatus.UNKNOWN


def test_whitespace_only_string_is_unknown():
    result = normalize_ingredient_name("   ")
    assert result.canonical_id is None
    assert result.status == NormalizationStatus.UNKNOWN


def test_malicious_input_is_handled_safely():
    malicious = "<script>alert('xss')</script>"
    result = normalize_ingredient_name(malicious)
    assert result.status == NormalizationStatus.UNKNOWN
    assert result.canonical_id is None


def test_very_long_input_does_not_crash():
    long_input = "a" * 10_000
    result = normalize_ingredient_name(long_input)
    assert result.status == NormalizationStatus.UNKNOWN


def test_normalize_pantry_dedupes_duplicates_to_one_canonical_id():
    result = normalize_pantry(["onion", "onions", "Onion "])
    assert result.canonical_ids == frozenset({"onion"})
    assert result.unresolved == ()


def test_normalize_pantry_tracks_unresolved_raw_names():
    result = normalize_pantry(["rice", "unobtainium"])
    assert result.canonical_ids == frozenset({"rice"})
    assert result.unresolved == ("unobtainium",)


def test_normalize_pantry_empty_list():
    result = normalize_pantry([])
    assert result.canonical_ids == frozenset()
    assert result.unresolved == ()


# --- salted/unsalted butter distinction (essential-ingredient audit, 2026-09-06) ---


def test_unsalted_butter_normalizes_to_its_own_distinct_id():
    result = normalize_ingredient_name("Unsalted Butter")
    assert result.canonical_id == "unsalted_butter"
    assert result.status == NormalizationStatus.EXACT


def test_salted_butter_normalizes_to_its_own_distinct_id():
    result = normalize_ingredient_name("Salted Butter")
    assert result.canonical_id == "salted_butter"
    assert result.status == NormalizationStatus.EXACT


def test_generic_butter_is_unaffected_by_the_salted_unsalted_addition():
    result = normalize_ingredient_name("Butter")
    assert result.canonical_id == "butter"
    assert result.status == NormalizationStatus.EXACT


def test_salted_and_unsalted_butter_never_collapse_into_each_other():
    salted = normalize_ingredient_name("salted butter")
    unsalted = normalize_ingredient_name("unsalted butter")
    assert salted.canonical_id == "salted_butter"
    assert unsalted.canonical_id == "unsalted_butter"
    assert salted.canonical_id != unsalted.canonical_id


# --- Priority-2 fix (PR #15 correction pass, 2026-09-08): singular raw ------
# name -> plural canonical entry (the reverse of the existing plural ->
# singular direction above). Uses the real grocery taxonomy
# (app.domain.grocery_taxonomy), since that is where the canonical id
# involved in the traced live bug ("chicken_wings") actually lives --
# not the small PP-001 recipe-normalization fixture the rest of this
# file defaults to.

from app.domain.grocery_taxonomy import CANONICAL_GROCERY_INGREDIENTS, GROCERY_INGREDIENT_ALIASES  # noqa: E402


def test_singular_raw_name_reaches_a_plural_canonical_entry():
    # Root cause of a real bug traced live 2026-09-08: a recipe's raw
    # "Chicken wing" (singular) previously fell through to UNKNOWN even
    # though the user's pantry had the same concept via "Chicken Wings"
    # (canonical id "chicken_wings", plural).
    result = normalize_ingredient_name(
        "Chicken wing", canonical_vocabulary=CANONICAL_GROCERY_INGREDIENTS, aliases=GROCERY_INGREDIENT_ALIASES
    )
    assert result.canonical_id == "chicken_wings"
    assert result.status == NormalizationStatus.EXACT


def test_plural_raw_name_still_matches_the_same_canonical_entry():
    result = normalize_ingredient_name(
        "Chicken Wings", canonical_vocabulary=CANONICAL_GROCERY_INGREDIENTS, aliases=GROCERY_INGREDIENT_ALIASES
    )
    assert result.canonical_id == "chicken_wings"
    assert result.status == NormalizationStatus.EXACT


def test_pantry_and_recipe_side_chicken_wing_variants_resolve_to_the_same_id():
    # The specific invariant the ticket requires: a trusted canonical
    # ingredient must classify as matched regardless of which
    # singular/plural spelling produced it.
    pantry_side = normalize_ingredient_name(
        "Chicken Wings", canonical_vocabulary=CANONICAL_GROCERY_INGREDIENTS, aliases=GROCERY_INGREDIENT_ALIASES
    )
    recipe_side = normalize_ingredient_name(
        "Chicken wing", canonical_vocabulary=CANONICAL_GROCERY_INGREDIENTS, aliases=GROCERY_INGREDIENT_ALIASES
    )
    assert pantry_side.canonical_id == recipe_side.canonical_id == "chicken_wings"


def test_generic_chicken_does_not_overmatch_to_a_specific_cut_via_pluralization():
    # Guardrail explicitly required by the ticket: pluralizing "chicken"
    # must not accidentally land on chicken_wings/chicken_breast/etc --
    # there is no bare "chicken" canonical id in the taxonomy at all, so
    # this must remain UNKNOWN, not silently guessed.
    result = normalize_ingredient_name(
        "chicken", canonical_vocabulary=CANONICAL_GROCERY_INGREDIENTS, aliases=GROCERY_INGREDIENT_ALIASES
    )
    assert result.canonical_id is None
    assert result.status == NormalizationStatus.UNKNOWN


def test_pluralization_is_not_attempted_for_already_plural_names():
    # _plural_candidates only fires when the cleaned name does not
    # already end in "s" -- an unresolvable plural-looking word must not
    # spuriously grow an extra "s".
    result = normalize_ingredient_name(
        "totally unknown thingamajigs",
        canonical_vocabulary=CANONICAL_GROCERY_INGREDIENTS,
        aliases=GROCERY_INGREDIENT_ALIASES,
    )
    assert result.canonical_id is None
    assert result.status == NormalizationStatus.UNKNOWN


def test_ground_beef_normalizes_to_minced_beef():
    # Regression: found live during PR #15 second correction pass
    # multi-anchor validation -- "ground beef" (both the US pantry term
    # and RecipeAPI.io's own ingredient text) previously fell through
    # to UNKNOWN despite "minced_beef" already being a real canonical
    # id, because only the UK term "Minced Beef" was an exact match.
    result = normalize_ingredient_name(
        "Ground beef", canonical_vocabulary=CANONICAL_GROCERY_INGREDIENTS, aliases=GROCERY_INGREDIENT_ALIASES
    )
    assert result.canonical_id == "minced_beef"
    assert result.status == NormalizationStatus.ALIAS


def test_ground_lamb_normalizes_to_minced_lamb():
    # Regression: found live during the lamb-family provider audit
    # (PR #15 sixth correction pass, 2026-09-08) -- "ground lamb"
    # (RecipeAPI.io's real ingredient text, 61 recipes confirmed live)
    # previously fell through to UNKNOWN despite "minced_lamb" already
    # being a real canonical id, because only "Minced lamb" was an
    # exact vocabulary match.
    result = normalize_ingredient_name(
        "Ground lamb", canonical_vocabulary=CANONICAL_GROCERY_INGREDIENTS, aliases=GROCERY_INGREDIENT_ALIASES
    )
    assert result.canonical_id == "minced_lamb"
    assert result.status == NormalizationStatus.ALIAS
