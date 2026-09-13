"""Bounded in-memory TTL cache for RecipeAPI.io ingredient-catalogue
lookups (ticket section 15, "Provider Mapping Cache").

Design choice, documented explicitly: a bounded IN-MEMORY TTL cache was
chosen over a persistent additive DB table. Both were acceptable per
the ticket ("Preferred: persistent additive cache if simple and safe.
Acceptable: bounded in-memory TTL cache if persistent storage would
create unnecessary risk"). In-memory was chosen because:

1. It requires zero schema migration, zero backup/rollback plan, and
   zero risk to the production database -- a meaningful reduction in
   surface area for an already large ticket.
2. The existing precedent in this exact codebase
   (app.repositories.runtime_ingredient_repository's merged-vocabulary
   cache) already uses this same bounded in-memory TTL pattern for a
   closely related concern (admin ingredient/alias lookups), so this
   keeps the caching strategy for "things that avoid a repeated
   lookup" consistent across the codebase rather than introducing a
   second, differently-shaped mechanism.
3. The cost of a cache miss after a process restart is small and
   bounded (one extra GET /ingredients call, itself cached again
   immediately) -- consistent with the competition deployment's
   existing single-process assumption (see app.rate_limit's own
   documented limitation).

Entries are keyed by the normalized query text actually sent to
GET /ingredients?search=. A resolution FAILURE (no safe match found) is
cached too (as an explicit "no match" sentinel), not just successes --
otherwise a term RecipeAPI.io's catalogue simply does not have would
be re-queried on every single request that mentions it, which is
exactly the repeated-lookup waste ticket section 25 asks to avoid.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.domain.ingredient_resolution import ProviderIngredient

_DEFAULT_TTL_SECONDS = 3600.0  # 1 hour: catalogue vocabulary changes rarely, if ever
_MAX_ENTRIES = 2000  # bounded (ticket section 15) -- evicts oldest on overflow


@dataclass(frozen=True)
class CachedProviderMatch:
    match: ProviderIngredient | None  # None means "looked up, no safe match found"
    # 2026-09-13 hotfix (generic-provider-direct-fallback): whether the
    # catalogue query returned ANY candidates at all, even when none of
    # them cleared a safe-match tier. This is what distinguishes an
    # ordinary broad real word ("chicken" -- the catalogue returns many
    # "Chicken X" entries) from a genuine typo ("chiken" -- the
    # catalogue returns nothing) without needing an LLM call to tell
    # them apart. Cached alongside `match` so a repeated lookup of the
    # same no-safe-match term does not need to re-query the catalogue
    # just to recover this signal.
    had_candidates: bool = False


_cache: dict[str, tuple[float, CachedProviderMatch]] = {}


def get_cached_match(query_key: str, *, ttl_seconds: float = _DEFAULT_TTL_SECONDS) -> CachedProviderMatch | None:
    """Returns None only when there is no (unexpired) cache entry at
    all -- distinct from a cached CachedProviderMatch(match=None),
    which means "already looked up, confirmed no safe match"."""

    entry = _cache.get(query_key)
    if entry is None:
        return None
    cached_at, value = entry
    if (time.monotonic() - cached_at) >= ttl_seconds:
        del _cache[query_key]
        return None
    return value


def set_cached_match(query_key: str, match: ProviderIngredient | None, *, had_candidates: bool = False) -> None:
    if len(_cache) >= _MAX_ENTRIES:
        oldest_key = min(_cache, key=lambda k: _cache[k][0])
        del _cache[oldest_key]
    _cache[query_key] = (time.monotonic(), CachedProviderMatch(match=match, had_candidates=had_candidates))


def clear_provider_ingredient_cache() -> None:
    """Test-only reset -- mirrors
    app.repositories.runtime_ingredient_repository.invalidate_runtime_ingredient_cache's
    shape for consistency."""

    _cache.clear()
