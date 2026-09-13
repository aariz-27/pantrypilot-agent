"""Bounded live test matrix for the unified ingredient resolution ticket
(section 30).

NOT part of the automated test suite -- never invoked by pytest or CI,
same convention as scripts/live_smoke_test_recipeapi.py. Run manually,
deliberately, and rarely:

    cd backend
    source .venv/bin/activate
    python scripts/live_ingredient_resolution_matrix.py

Requires RECIPEAPI_IO_API_KEY in backend/.env. ANTHROPIC_API_KEY is
optional -- without it, the four typo cases (I/J/K/L) simply fall back
to UNRESOLVED (ticket section 24's documented no-LLM fallback), which
is itself a valid, reportable outcome.

Runs the SAME resolution primitives the live orchestrator uses
(app.agent.ingredient_resolution, app.integrations.provider_ingredient_cache)
so a term already resolved for an earlier case in this run is never
looked up again -- ticket section 25/30's "avoid repeated equivalent
API calls" requirement. Never prints, logs, or otherwise exposes any
secret value.
"""

from __future__ import annotations

import asyncio

from app.agent.ingredient_resolution import resolve_pantry_ingredient, resolve_provider_search_term
from app.config import get_settings
from app.domain.ingredient_normalizer import normalize_ingredient_name
from app.integrations.llm_provider import AnthropicLLMProvider
from app.integrations.provider_ingredient_cache import clear_provider_ingredient_cache
from app.integrations.recipeapi_io import RecipeAPIIOAdapter
from app.recipe.provider import SearchStrategy
from app.repositories.runtime_ingredient_repository import get_merged_vocabulary

CASES: list[tuple[str, list[str]]] = [
    ("A", ["chicken"]),
    ("B", ["lamb"]),
    ("C", ["lamb chop"]),
    ("D", ["lamb chops"]),
    ("E", ["lamb chops", "rice"]),
    ("F", ["chicken breast"]),
    ("G", ["chicken breast", "rice"]),
    ("H", ["mutton"]),
    ("I", ["chiken"]),
    ("J", ["chiken brest"]),
    ("K", ["muton"]),
    ("L", ["basmti rice"]),
]


async def resolve_one(term, vocabulary, catalogue_lookup, llm_provider):
    """Mirrors AgentOrchestrator._init_state's per-term resolution,
    then AgentOrchestrator._resolve_outbound_provider_term's grounding
    of the resulting identity into a provider search term."""

    local = normalize_ingredient_name(term, vocabulary.canonical_ids, vocabulary.aliases)
    if local.canonical_id is not None:
        identity = local.canonical_id
        local_desc = f"{local.canonical_id} ({local.status.value})"
        llm_note = None
    else:
        resolution = await resolve_pantry_ingredient(
            term,
            vocabulary.canonical_ids,
            vocabulary.aliases,
            catalogue_lookup=catalogue_lookup,
            llm_provider=llm_provider,
        )
        identity = resolution.canonical_id or resolution.search_anchor_identity
        local_desc = f"unresolved locally -> state={resolution.state.value}"
        llm_note = resolution.state.value if resolution.state.value == "llm_corrected_and_grounded" else None

    if identity is None:
        return identity, local_desc, llm_note, None

    provider_resolution = await resolve_provider_search_term(identity, catalogue_lookup)
    return identity, local_desc, llm_note, provider_resolution.provider_term


async def main() -> None:
    settings = get_settings()
    if not settings.recipeapi_io_configured:
        print("RECIPEAPI_IO_API_KEY is not configured in backend/.env -- aborting live test matrix.")
        return

    llm_provider = AnthropicLLMProvider(settings) if settings.llm_configured else None
    if llm_provider is None:
        print(
            "ANTHROPIC_API_KEY is not configured -- typo cases (I/J/K/L) will report "
            "UNRESOLVED via the documented no-LLM fallback (ticket section 24), not an error.\n"
        )

    vocabulary = get_merged_vocabulary(None)
    clear_provider_ingredient_cache()
    request_count = 0

    async with RecipeAPIIOAdapter(settings) as adapter:
        async def counted_catalogue_lookup(query: str):
            nonlocal request_count
            request_count += 1
            return await adapter.search_ingredients(query)

        for label, raw_terms in CASES:
            print(f"=== Case {label}: {raw_terms} ===")
            provider_terms: list[str] = []
            for term in raw_terms:
                identity, local_desc, llm_note, provider_term = await resolve_one(
                    term, vocabulary, counted_catalogue_lookup, llm_provider,
                )
                print(f"  raw={term!r}")
                print(f"    local_resolution={local_desc}")
                print(f"    llm_correction={llm_note}")
                print(f"    final_provider_term={provider_term!r}")
                if provider_term is not None:
                    provider_terms.append(provider_term)

            if not provider_terms:
                print("  -> UNRESOLVED: no provider term available, no recipe search performed.")
                print()
                continue

            result = await adapter.search(SearchStrategy(query_ingredients=provider_terms, page_size=10))
            request_count += 1
            print(f"  query_ingredients={provider_terms}")
            print(f"  raw_provider_recipe_count={len(result.items)} has_more={result.has_more}")
            print()

    print(f"Total live requests used: {request_count}")
    print("No secret value was printed by this script.")


if __name__ == "__main__":
    asyncio.run(main())
