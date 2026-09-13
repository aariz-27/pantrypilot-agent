"""Ingredient resolution diagnostics + safe provider-name matching
(2026-09-13 unified ingredient resolution ticket).

Pure, I/O-free domain layer -- mirrors the existing convention
(app.domain.ingredient_normalizer takes vocabulary as a parameter and
never touches a database or network; this module is the same shape for
the NEW provider-catalogue-matching and diagnostics concerns this
ticket adds).

Architectural principle (ticket section 1) this module exists to keep
distinct and never conflate:

    A. USER INPUT               "chiken brest"
    B. INTERPRETED USER INTENT  "chicken breast"      (typo correction, if used)
    C. PANTRYPILOT CANONICAL ID  chicken_breast        (local/admin taxonomy)
    D. RECIPEAPI PROVIDER TERM  "Chicken breast"       (what reaches the provider)
    E. LOCAL PRICING IDENTITY    chicken_breast         (== C, never D)

Nothing in this module ever assigns or reads a pricing identity --
pricing stays exclusively governed by
app.domain.ingredient_normalizer.normalize_ingredient_name against the
local/admin taxonomy (app.repositories.runtime_ingredient_repository),
completely independent of whatever provider-facing term this module
produces for a RecipeAPI.io search. See app.domain.cost_engine: a
`RecipeIngredient.canonical_id` of None is always priced as
UNKNOWN, never zero -- this module never sets that field.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class IngredientResolutionState(str, Enum):
    """Diagnostic-only classification of how one pantry/anchor term was
    resolved (ticket section 26) -- never shown verbatim to end users,
    but tests and logs can assert on it precisely."""

    LOCAL_EXACT = "local_exact"
    LOCAL_ALIAS = "local_alias"
    PROVIDER_DIRECT = "provider_direct"
    PROVIDER_CATALOG_RESOLVED = "provider_catalog_resolved"
    LLM_CORRECTED_AND_GROUNDED = "llm_corrected_and_grounded"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class ProviderIngredient:
    """One row from RecipeAPI.io's GET /ingredients?search= catalogue
    (app.integrations.recipeapi_io.RecipeAPIIOAdapter.search_ingredients)."""

    provider_id: str
    name: str
    category: str | None


def humanize_for_provider(text: str) -> str:
    """Safe, deterministic fallback formatting only (ticket section 7):
    snake_case/hyphenated internal identity -> natural spaced text.
    This alone is NOT sufficient provider-vocabulary resolution (a
    canonical id's own plural/singular form frequently does not match
    RecipeAPI.io's own ingredient vocabulary -- confirmed live,
    2026-09-13: "lamb_chops" -> "lamb chops" still returns zero RecipeAPI
    results; the provider's own catalogue lists the singular "Lamb
    chop") -- callers needing real provider-vocabulary grounding must
    also consult select_safe_provider_match against the live catalogue.
    """

    return text.replace("_", " ").replace("-", " ").strip()


def _normalize_for_comparison(text: str) -> str:
    return " ".join(text.strip().lower().replace("_", " ").replace("-", " ").split())


def _singular_plural_variants(text: str) -> set[str]:
    variants = {text}
    if text.endswith("es") and len(text) > 3:
        variants.add(text[:-2])
    if text.endswith("s") and len(text) > 2:
        variants.add(text[:-1])
    if not text.endswith("s"):
        variants.add(f"{text}s")
    return variants


def singular_plural_query_variants(text: str) -> list[str]:
    """Deterministic alternate spelling(s) of `text` worth trying as a
    SEPARATE catalogue query when the original spelling's query returns
    no safe match (ticket section 16's "safe deterministic singular/
    plural equivalent," applied at the QUERY level rather than only at
    the candidate-matching level below).

    Confirmed live, 2026-09-13: RecipeAPI.io's own GET /ingredients
    search does not stem plurals server-side -- querying "lamb chops"
    (the naive humanization of PantryPilot's canonical id lamb_chops)
    returns ZERO candidates, even though the provider's own catalogue
    lists the singular "Lamb chop" (confirmed via a direct live call).
    select_safe_provider_match's own candidate-level singular/plural
    comparison can never help in that case, because the plural query
    never returns that candidate to compare against in the first place.
    Ordered, deterministic, and excludes `text` itself -- typically at
    most one variant (e.g. stripping a trailing "s"), occasionally two.
    """

    normalized = _normalize_for_comparison(text)
    if not normalized:
        return []
    return sorted(_singular_plural_variants(normalized) - {normalized})


def select_safe_provider_match(
    query: str, candidates: list[ProviderIngredient]
) -> tuple[ProviderIngredient | None, IngredientResolutionState]:
    """Safe-matching tiers (ticket section 16) -- never the first raw
    result, never a fuzzy/substring/semantic guess. Each tier only ever
    accepts a candidate whose NORMALIZED name is exactly (not
    approximately) equal to the query or a deterministic singular/
    plural variant of it -- this is what makes "lamb chops" safely
    resolve to "Lamb chop" while never letting "lamb chops" resolve to
    the semantically different "Lamb liver" or "chicken" resolve to
    "Chicken broth" merely because the text overlaps (ticket's own
    explicit counter-examples): neither of those ever becomes exactly
    equal to the query or one of its singular/plural variants.

    Returns (None, UNRESOLVED) when no candidate clears any tier --
    the caller must never fall back to picking "the first result" or a
    substring match itself.

    Returns (None, AMBIGUOUS) when the SAME best tier is satisfied by
    more than one candidate with genuinely different identities (ticket
    section 11: "chik" must not silently become one specific chicken
    cut) -- distinct from UNRESOLVED so a caller can choose to surface
    clarification options rather than a plain "not found".
    """

    normalized_query = _normalize_for_comparison(query)
    if not normalized_query or not candidates:
        return None, IngredientResolutionState.UNRESOLVED

    query_variants = _singular_plural_variants(normalized_query)

    # Tier 1+2 combined: exact / case-insensitive normalized match --
    # comparison is already case-insensitive via _normalize_for_comparison.
    exact_matches = [c for c in candidates if _normalize_for_comparison(c.name) == normalized_query]
    if len(exact_matches) == 1:
        return exact_matches[0], IngredientResolutionState.PROVIDER_CATALOG_RESOLVED
    if len(exact_matches) > 1:
        return None, IngredientResolutionState.AMBIGUOUS

    # Tier 3+4: deterministic singular/plural equivalent (covers the
    # confirmed live gap: PantryPilot's plural cut names, e.g.
    # "lamb_chops", vs. RecipeAPI.io's singular catalogue entry "Lamb
    # chop").
    variant_matches = [c for c in candidates if _normalize_for_comparison(c.name) in query_variants]
    if len(variant_matches) == 1:
        return variant_matches[0], IngredientResolutionState.PROVIDER_CATALOG_RESOLVED
    if len(variant_matches) > 1:
        return None, IngredientResolutionState.AMBIGUOUS

    return None, IngredientResolutionState.UNRESOLVED
