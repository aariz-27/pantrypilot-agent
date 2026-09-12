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
# Kept as SearchStrategy's own default (unchanged) so any caller that
# constructs one without specifying page_size keeps the historically
# safe free-plan value; app.agent.orchestrator explicitly overrides
# this per-request from Settings.recipeapi_page_size (2026-09-13
# quota-aware recommendation-depth revision).
MAX_PAGE_SIZE = 10

# Structural safety ceiling only -- NOT a claim about what any specific
# plan supports. Settings.recipeapi_page_size (app.config) is where the
# actual per-deployment value is tuned; this just bounds Pydantic
# validation against a wildly wrong configuration value (e.g. a typo
# adding an extra zero) from ever reaching a provider request at all.
# Confirmed live (2026-09-13, one bounded call) that the active trial
# accepts and honors per_page=25; this ceiling is deliberately well
# above that so a plan upgrade never requires touching this constant.
ABSOLUTE_MAX_PAGE_SIZE = 100

# PR #15 fifth correction pass (2026-09-08, product decision): a small,
# reviewed, ONE-DIRECTIONAL mapping from canonical id to an alternate
# provider-search term. Lives here (the provider-NEUTRAL module), not
# inside any one concrete adapter, so both provider implementations and
# the agent/observation layer can reference the exact same reviewed set
# without the agent layer ever depending on a specific concrete provider
# (docs/API_INTEGRATION_STANDARDS.md: downstream code must not ask "was
# this RecipeAPI.io?"). Consulted ONLY when a caller explicitly opts in
# (SearchStrategy.broaden_provider_search); NEVER consulted by canonical
# matching/normalization (app.domain.ingredient_normalizer), which stays
# exact and completely independent of this.
#
# Product decision (2026-09-08, fifth correction pass): this dict holds
# ONLY true lexical/synonym rewordings of the SAME ingredient -- never a
# specific-ingredient-to-broader-parent-category rewrite. Broadening
# specificity purely to manufacture a larger result set was found live
# to be actively counterproductive (basmati_rice -> "rice" pulled in
# ~1400 results, nearly all sticky rice / rice noodles / rice paper --
# genuinely different foods that do not canonically match basmati rice
# at all) and is a real product-truthfulness regression, not merely an
# efficiency concern: PantryPilot must prefer fewer genuinely relevant
# results over more weakly-related ones. minced_beef -> "ground beef" is
# kept because it is the SAME specific ingredient under its other
# common name (a UK/US wording difference, not a category change) --
# see the entries REMOVED below for the ones that were category
# changes, kept here as a record of what was reviewed and rejected:
#   basmati_rice -> "rice"   (specific rice variety -> generic rice)
#   jasmine_rice -> "rice"   (specific rice variety -> generic rice)
#   white_rice   -> "rice"   (specific rice variety -> generic rice)
# Specific animal cuts (chicken_wings, chicken_breast, chicken_thigh,
# lamb_cubes, ...) were never in this dict and must never be added --
# broadening a cut to its generic parent (e.g. "chicken", "lamb") is
# exactly the specificity loss this mapping must never introduce.
PROVIDER_SEARCH_TERM_OVERRIDES: dict[str, str] = {
    "minced_beef": "ground beef",
}


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
    page_size: int = Field(default=MAX_PAGE_SIZE, ge=1, le=ABSOLUTE_MAX_PAGE_SIZE)
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
    # PR #15 fourth correction pass (2026-09-08, Blocker 2): opt-in,
    # agent-controlled request to use a REVIEWED broader provider-search
    # term for the anchor when one exists (e.g. "basmati_rice" -> "rice")
    # -- never invented, never automatic. This only ever changes what
    # TEXT is sent to the provider; canonical matching (pantry match,
    # anchor-presence, scoring) always continues to use the exact
    # canonical id, completely unaffected by this flag. See
    # RecipeAPIIOAdapter's PROVIDER_SEARCH_TERM_OVERRIDES for the
    # reviewed mapping and why some ids (e.g. chicken_wings) are
    # deliberately absent from it. Costs zero extra requests -- it
    # changes the TEXT of the same primary query, not its count.
    broaden_provider_search: bool = False

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
