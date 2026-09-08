"""Provider-neutral RecipeProvider abstraction (M04 foundation).

Per TECHNICAL_SPEC.md section 10 and docs/API_INTEGRATION_STANDARDS.md
section 18: every recipe source is accessed through this one contract
and must return only the internal Recipe / SearchResult types defined
here -- never a provider-specific payload shape. Downstream code (the
future agent/tools, and today's deterministic core from PP-001) must
never depend on which concrete provider produced a Recipe, except where
provenance/display explicitly needs source identity (already carried on
the Recipe DTO itself via `provider`/`provider_recipe_id`).

This module intentionally does not implement a generic
plugin/registry framework -- PantryPilot has exactly two providers
(RecipeAPI.io, LocalCuratedRecipeProvider) and a `Protocol` is
sufficient structural typing for that.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.models import Recipe

# RecipeAPI.io's free plan caps per_page at 10 (confirmed against live
# provider documentation, 2026-09-05); this is also the page size
# TECHNICAL_SPEC.md section 10 recommends as "normal" for any plan.
MAX_PAGE_SIZE = 10


class SearchStrategy(BaseModel):
    """Provider-neutral search request.

    Choosing *which* strategy to use (anchor ingredient, pagination,
    reformulation, cuisine filter) is the future agent's job (M03, not
    part of this ticket). This type is just the typed shape a caller
    (agent, or today's tests/smoke script) uses to ask a provider to
    search; it does not itself decide search policy.
    """

    model_config = ConfigDict(frozen=True)

    query_ingredients: list[str] = Field(default_factory=list)
    cuisine: str | None = None
    max_prep_time_minutes: int | None = Field(default=None, gt=0)
    page: int = Field(default=1, ge=1, le=1000)
    page_size: int = Field(default=MAX_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)
    # Priority-1 efficiency fix (PR #15 correction pass, 2026-09-08): the
    # RecipeAPI.io adapter's ingredients filter can silently contribute
    # zero relevance for some well-represented pantry ingredient terms
    # (see RecipeAPIIOAdapter.enrich_with_free_text_search's docstring).
    # This used to run unconditionally on every search, doubling
    # RecipeAPI.io request volume regardless of need. It is now an
    # explicit, agent-controlled opt-in (app.agent.actions.SearchArgs)
    # so the LLM -- which DEC-005 assigns search-strategy control to --
    # requests it only when the deterministic observation evidence
    # (poor_pantry_overlap / zero feasible candidates) indicates the
    # primary query under-represented the user's actual pantry. Default
    # False: a normal search never pays the extra request.
    enrich_free_text: bool = False

    @field_validator("query_ingredients")
    @classmethod
    def _validate_ingredients(cls, value: list[str]) -> list[str]:
        cleaned = [v.strip() for v in value if v and v.strip()]
        if len(cleaned) > 30:
            raise ValueError("query_ingredients must not exceed 30 items")
        return cleaned


class SearchResultItem(BaseModel):
    """Lightweight search-result identity, before fetching full detail.

    Provider-neutral: only fields already present on the Recipe DTO's
    identity/display surface are exposed here.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    provider: str
    provider_recipe_id: str
    name: str
    image_url: str | None = None
    cuisine: str | None = None
    # Priority-1 efficiency fix (PR #15 correction pass, 2026-09-08): set
    # ONLY when the provider's search/list response for this item already
    # contained a complete recipe object (ingredients + instructions),
    # not merely display metadata -- confirmed live for RecipeAPI.io
    # (2026-09-08: /recipes list items carry the exact same fields as
    # /recipes/{id} detail items). When present, app.agent.tools skips
    # the separate get_details() round trip entirely for this candidate.
    # Never fabricated/guessed: a provider whose list response is
    # genuinely lightweight (or an item missing ingredients/instructions)
    # simply leaves this None, and the normal get_details() fallback
    # runs unchanged.
    full_recipe: Recipe | None = None


class SearchResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[SearchResultItem]
    page: int
    page_size: int
    has_more: bool


@runtime_checkable
class RecipeProvider(Protocol):
    """Structural contract every recipe source implements.

    Implementations own: provider calls, response validation,
    provider-to-domain mapping, provenance, pagination mechanics,
    timeout/retry enforcement, and typed error mapping. They must never
    leak provider-specific fields past this boundary.
    """

    provider_name: str

    async def search(self, strategy: SearchStrategy) -> SearchResult: ...

    async def get_details(self, provider_recipe_id: str) -> Recipe: ...


def dedupe_search_results(items: list[SearchResultItem]) -> list[SearchResultItem]:
    """Remove duplicate items by (provider, provider_recipe_id) identity,
    preserving first-seen order. Overlapping results across pages/
    strategies are a normal provider behavior this layer must handle;
    cross-provider fuzzy deduplication is explicitly out of scope."""

    seen: set[tuple[str, str]] = set()
    deduped: list[SearchResultItem] = []
    for item in items:
        key = (item.provider, item.provider_recipe_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
