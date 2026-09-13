"""Bounded live verification for the generic-provider-direct-fallback
hotfix (ticket section 11).

NOT part of the automated test suite -- never invoked by pytest or CI,
same convention as scripts/live_smoke_test_recipeapi.py and
scripts/live_ingredient_resolution_matrix.py. Run manually, deliberately,
and rarely:

    cd backend
    source .venv/bin/activate
    python scripts/live_generic_provider_direct_matrix.py

Requires RECIPEAPI_IO_API_KEY in backend/.env. ANTHROPIC_API_KEY is
optional -- without it the typo case ("chiken brest") reports
UNRESOLVED via the documented no-LLM fallback, which is itself a valid
result to report.

Kept minimal (ticket section 11's own instruction): does NOT run the
full agent loop with a real LLM decide() call -- only the deterministic
resolution primitives, one recipe search per case, and detail fetches
for a small bounded sample (first 3 results) to compute a real,
deterministic feasible count via app.agent.tools.evaluate_and_rank.
No recipe content, price, or ingredient identity is fabricated by this
script -- everything printed is either grounded via RecipeAPI.io or
computed deterministically from what it actually returned.
"""

from __future__ import annotations

import asyncio

from app.agent.ingredient_resolution import resolve_pantry_ingredient, resolve_provider_search_term
from app.agent.tools import evaluate_and_rank
from app.config import get_settings
from app.db.connection import connection_scope
from app.db.schema import create_schema
from app.domain.ingredient_normalizer import normalize_ingredient_name
from app.domain.models import UserConstraints
from app.integrations.llm_provider import AnthropicLLMProvider
from app.integrations.provider_ingredient_cache import clear_provider_ingredient_cache
from app.integrations.recipeapi_io import RecipeAPIIOAdapter
from app.recipe.provider import SearchStrategy
from app.repositories.price_repository import PriceRepository
from app.repositories.runtime_ingredient_repository import get_merged_vocabulary

CASES: list[str] = ["chicken", "lamb", "lamb chops", "chicken breast", "chiken brest"]
DETAIL_FETCH_SAMPLE_SIZE = 3  # bounded -- ticket section 11: "use minimal calls"


async def main() -> None:
    settings = get_settings()
    if not settings.recipeapi_io_configured:
        print("RECIPEAPI_IO_API_KEY is not configured in backend/.env -- aborting live verification.")
        return

    llm_provider = AnthropicLLMProvider(settings) if settings.llm_configured else None
    if llm_provider is None:
        print("ANTHROPIC_API_KEY is not configured -- 'chiken brest' will report UNRESOLVED (documented fallback).\n")

    vocabulary = get_merged_vocabulary(None)
    clear_provider_ingredient_cache()

    temp_db_path = "/tmp/pantrypilot_live_matrix_scratch.db"
    with connection_scope(temp_db_path, read_only=False) as connection:
        create_schema(connection)
    price_repository = PriceRepository(temp_db_path)

    constraints = UserConstraints(max_total_time_minutes=120)
    request_count = 0
    llm_correction_calls = 0

    async with RecipeAPIIOAdapter(settings) as adapter:
        original_correction = llm_provider.propose_ingredient_correction if llm_provider else None

        async def counted_correction(request):
            nonlocal llm_correction_calls
            llm_correction_calls += 1
            return await original_correction(request)

        if llm_provider is not None:
            llm_provider.propose_ingredient_correction = counted_correction  # type: ignore[method-assign]

        async def counted_catalogue_lookup(query: str):
            nonlocal request_count
            request_count += 1
            return await adapter.search_ingredients(query)

        for term in CASES:
            print(f"=== {term!r} ===")
            ingredients_called_before = request_count
            llm_before = llm_correction_calls

            local = normalize_ingredient_name(term, vocabulary.canonical_ids, vocabulary.aliases)
            if local.canonical_id is not None:
                identity, resolution_desc = local.canonical_id, f"local:{local.canonical_id}"
            else:
                resolution = await resolve_pantry_ingredient(
                    term, vocabulary.canonical_ids, vocabulary.aliases,
                    catalogue_lookup=counted_catalogue_lookup, llm_provider=llm_provider,
                )
                identity = resolution.canonical_id or resolution.search_anchor_identity
                resolution_desc = f"state={resolution.state.value}"

            ingredients_called = request_count > ingredients_called_before
            llm_called = llm_correction_calls > llm_before
            print(f"  resolution: {resolution_desc}")
            print(f"  /ingredients called: {ingredients_called}")
            print(f"  LLM called: {llm_called}")

            if identity is None:
                print("  final provider term: None -- UNRESOLVED, no /recipes call performed")
                print()
                continue

            provider_resolved = await resolve_provider_search_term(identity, counted_catalogue_lookup)
            provider_term = provider_resolved.provider_term
            print(f"  final provider term: {provider_term!r}")

            result = await adapter.search(SearchStrategy(query_ingredients=[provider_term], page_size=10))
            request_count += 1
            print(f"  /recipes called: True")
            print(f"  raw_recipe_count: {len(result.items)}")

            sample_ids = [item.provider_recipe_id for item in result.items[:DETAIL_FETCH_SAMPLE_SIZE]]
            recipes = []
            for provider_recipe_id in sample_ids:
                recipe = await adapter.get_details(provider_recipe_id)
                request_count += 1
                recipes.append(recipe)
            feasible, _rejected = evaluate_and_rank(recipes, frozenset(), constraints, price_repository)
            print(
                f"  feasible_count: {len(feasible)} "
                f"(out of a bounded sample of {len(recipes)}/{len(result.items)} raw results, empty pantry)"
            )
            print()

    print(f"Total live RecipeAPI.io requests used: {request_count}")
    print(f"Total live LLM correction calls used: {llm_correction_calls}")
    print("No secret value was printed by this script.")


if __name__ == "__main__":
    asyncio.run(main())
