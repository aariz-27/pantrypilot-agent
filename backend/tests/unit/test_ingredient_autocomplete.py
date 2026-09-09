from app.domain.ingredient_autocomplete import (
    MAX_SUGGESTION_LIMIT,
    humanize_canonical_id,
    suggest_ingredients,
)


def test_humanize_canonical_id_formats_snake_case_as_title_case():
    assert humanize_canonical_id("basmati_rice") == "Basmati Rice"
    assert humanize_canonical_id("onion") == "Onion"


def test_exact_and_prefix_matches_rank_before_substring_matches():
    results = suggest_ingredients("onion")
    assert results
    assert results[0].display_name.lower() == "onion"


def test_alias_query_resolves_to_its_canonical_target():
    results = suggest_ingredients("capsicum")
    assert any(r.canonical_id == "bell_pepper" for r in results)


def test_empty_query_returns_no_suggestions():
    assert suggest_ingredients("") == []
    assert suggest_ingredients("   ") == []


def test_no_match_returns_empty_list():
    assert suggest_ingredients("zzzznotarealingredientzzzz") == []


def test_result_count_is_bounded_by_limit():
    results = suggest_ingredients("a", limit=3)
    assert len(results) <= 3


def test_limit_is_capped_at_max_even_if_caller_asks_for_more():
    results = suggest_ingredients("a", limit=1000)
    assert len(results) <= MAX_SUGGESTION_LIMIT


def test_matching_is_case_insensitive():
    lower = suggest_ingredients("onion")
    upper = suggest_ingredients("ONION")
    assert [r.canonical_id for r in lower] == [r.canonical_id for r in upper]


def test_duplicate_canonical_id_never_appears_twice():
    results = suggest_ingredients("o")
    ids = [r.canonical_id for r in results]
    assert len(ids) == len(set(ids))


def test_never_suggests_a_canonical_id_outside_the_approved_taxonomy():
    from app.domain.grocery_taxonomy import CANONICAL_GROCERY_INGREDIENTS

    results = suggest_ingredients("a", limit=MAX_SUGGESTION_LIMIT)
    assert all(r.canonical_id in CANONICAL_GROCERY_INGREDIENTS for r in results)
