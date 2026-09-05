"""Manual live RecipeAPI.io smoke test.

NOT part of the automated test suite. Never invoked by pytest or CI --
docs/API_INTEGRATION_STANDARDS.md section 18 / TECHNICAL_SPEC.md
section 18 prohibit consuming live provider quota in routine automated
tests. Run manually, deliberately, and rarely:

    cd backend
    source .venv/bin/activate
    python scripts/live_smoke_test_recipeapi.py

Requires RECIPEAPI_IO_API_KEY to be set in backend/.env (untracked,
gitignored). This script never prints, logs, or otherwise exposes the
key value. It performs a small, bounded number of real HTTP requests --
do not add loops, broad exploratory scraping, or deep pagination here.
"""

from __future__ import annotations

import asyncio

from app.config import get_settings
from app.integrations.recipeapi_io import RecipeAPIIOAdapter
from app.recipe.provider import SearchStrategy


async def main() -> None:
    request_count = 0
    settings = get_settings()
    if not settings.recipeapi_io_configured:
        print("RECIPEAPI_IO_API_KEY is not configured in backend/.env -- aborting smoke test.")
        return

    async with RecipeAPIIOAdapter(settings) as adapter:
        print("[1] Searching for ingredient='chicken' ...")
        result = await adapter.search(SearchStrategy(query_ingredients=["chicken"], page_size=3))
        request_count += 1
        print(f"    got {len(result.items)} result(s), has_more={result.has_more}")
        for item in result.items:
            print(f"    - id={item.id!r} name={item.name!r} cuisine={item.cuisine!r}")

        if not result.items:
            print("No search results returned -- cannot proceed to detail/provenance checks.")
        else:
            first = result.items[0]
            print(f"[2] Fetching details for provider_recipe_id={first.provider_recipe_id!r} ...")
            recipe = await adapter.get_details(first.provider_recipe_id)
            request_count += 1
            print(f"    provider={recipe.provider!r} provider_recipe_id={recipe.provider_recipe_id!r}")
            print(f"    id={recipe.id!r} name={recipe.name!r}")
            print(f"    cuisine={recipe.cuisine!r} category={recipe.category!r}")
            print(
                f"    prep_time_minutes={recipe.prep_time_minutes!r} "
                f"cook_time_minutes={recipe.cook_time_minutes!r}"
            )
            print(f"    ingredient_count={len(recipe.ingredients)}")
            print(
                "    provenance ok: "
                f"provider_set={bool(recipe.provider)} "
                f"provider_recipe_id_set={bool(recipe.provider_recipe_id)} "
                f"name_set={bool(recipe.name)}"
            )

        print("[3] Searching with cuisine filter='Italian' to check cuisine-filter parameter behavior ...")
        cuisine_result = await adapter.search(SearchStrategy(cuisine="Italian", page_size=3))
        request_count += 1
        cuisines_seen = [item.cuisine for item in cuisine_result.items]
        print(f"    got {len(cuisine_result.items)} result(s); cuisines observed: {cuisines_seen}")

    print(f"\nTotal live requests used: {request_count}")
    print("No secret value was printed by this script.")


if __name__ == "__main__":
    asyncio.run(main())
