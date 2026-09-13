from __future__ import annotations

import pytest

from app.domain.ingredient_resolution import ProviderIngredient
from app.integrations.provider_ingredient_cache import (
    clear_provider_ingredient_cache,
    get_cached_match,
    set_cached_match,
)


@pytest.fixture(autouse=True)
def _clear():
    clear_provider_ingredient_cache()
    yield
    clear_provider_ingredient_cache()


def test_miss_returns_none():
    assert get_cached_match("chicken") is None


def test_hit_returns_the_cached_match():
    match = ProviderIngredient("125", "Chicken", "poultry")
    set_cached_match("chicken", match)
    cached = get_cached_match("chicken")
    assert cached is not None
    assert cached.match == match


def test_a_no_match_result_is_cached_too():
    set_cached_match("zzznotreal", None)
    cached = get_cached_match("zzznotreal")
    assert cached is not None
    assert cached.match is None


def test_expired_entry_is_treated_as_a_miss():
    set_cached_match("chicken", ProviderIngredient("125", "Chicken", "poultry"))
    assert get_cached_match("chicken", ttl_seconds=0.0) is None


def test_clear_removes_everything():
    set_cached_match("chicken", ProviderIngredient("125", "Chicken", "poultry"))
    clear_provider_ingredient_cache()
    assert get_cached_match("chicken") is None


def test_had_candidates_defaults_to_false():
    set_cached_match("zzznotreal", None)
    assert get_cached_match("zzznotreal").had_candidates is False


def test_had_candidates_is_cached_for_a_no_safe_match_result():
    # 2026-09-13 hotfix: a broad real word ("chicken") whose catalogue
    # query returns candidates but no single safe exact/variant match
    # must be distinguishable, even from cache, from a genuine typo
    # whose catalogue query returns nothing at all.
    set_cached_match("chicken", None, had_candidates=True)
    cached = get_cached_match("chicken")
    assert cached.match is None
    assert cached.had_candidates is True
