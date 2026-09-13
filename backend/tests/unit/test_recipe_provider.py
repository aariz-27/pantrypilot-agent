import pytest

from app.recipe.provider import ABSOLUTE_MAX_PAGE_SIZE, MAX_PAGE_SIZE, SearchResultItem, SearchStrategy, dedupe_search_results


def test_search_strategy_defaults_are_bounded():
    strategy = SearchStrategy()
    assert strategy.page == 1
    assert strategy.page_size == MAX_PAGE_SIZE  # unchanged default (10) when not overridden


def test_search_strategy_accepts_a_larger_configured_page_size():
    # 2026-09-13 quota-aware recommendation-depth revision: page_size is
    # now genuinely configurable per deployment (Settings.recipeapi_page_size),
    # not hard-clamped back to the old free-plan MAX_PAGE_SIZE. 25 is the
    # value confirmed live against the active RecipeAPI.io trial.
    strategy = SearchStrategy(page_size=25)
    assert strategy.page_size == 25


def test_search_strategy_rejects_oversized_page_size():
    with pytest.raises(Exception):
        SearchStrategy(page_size=ABSOLUTE_MAX_PAGE_SIZE + 1)


def test_search_strategy_rejects_zero_or_negative_page():
    with pytest.raises(Exception):
        SearchStrategy(page=0)


def test_search_strategy_cleans_blank_ingredients():
    strategy = SearchStrategy(query_ingredients=["  rice  ", "", "   ", "garlic"])
    assert strategy.query_ingredients == ["rice", "garlic"]


def test_search_strategy_rejects_too_many_ingredients():
    with pytest.raises(Exception):
        SearchStrategy(query_ingredients=[f"item{i}" for i in range(31)])


def _item(provider="recipeapi_io", provider_recipe_id="1", name="A"):
    return SearchResultItem(
        id=f"{provider}:{provider_recipe_id}",
        provider=provider,
        provider_recipe_id=provider_recipe_id,
        name=name,
    )


def test_dedupe_search_results_removes_duplicate_identity():
    items = [_item(provider_recipe_id="1"), _item(provider_recipe_id="1"), _item(provider_recipe_id="2")]
    deduped = dedupe_search_results(items)
    assert [i.provider_recipe_id for i in deduped] == ["1", "2"]


def test_dedupe_search_results_preserves_first_seen_order():
    a = _item(provider_recipe_id="1", name="First")
    b = _item(provider_recipe_id="1", name="Second (duplicate id, different payload)")
    deduped = dedupe_search_results([a, b])
    assert len(deduped) == 1
    assert deduped[0].name == "First"


def test_dedupe_search_results_distinguishes_by_provider_too():
    a = _item(provider="recipeapi_io", provider_recipe_id="1")
    b = _item(provider="local_curated", provider_recipe_id="1")
    deduped = dedupe_search_results([a, b])
    assert len(deduped) == 2


def test_supported_strict_cuisines_matches_recipeapi_documented_enum():
    from app.recipe.provider import SUPPORTED_STRICT_CUISINES

    assert SUPPORTED_STRICT_CUISINES == frozenset(
        {
            "american", "chinese", "french", "greek", "italian", "japanese",
            "mexican", "portuguese", "spanish", "thai", "turkish",
        }
    )
    # Explicitly excluded (never silently invented as a supported value).
    for unsupported in ("indian", "pakistani", "asian", "mediterranean", "desi"):
        assert unsupported not in SUPPORTED_STRICT_CUISINES
