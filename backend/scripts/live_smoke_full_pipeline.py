"""Manual, one-off live A-D integration smoke test (Founder-authorized
full Modules A-D validation, 2026-09-07).

Exercises the REAL, connected pipeline: AgentOrchestrator ->
AnthropicLLMProvider (real Anthropic API) -> RecipeAPIIOAdapter (real
RecipeAPI.io) -> the deterministic Module A-C pipeline (normalization,
pantry matching, PriceRepository against the real packaged reference
DB, cost engine, constraint evaluator, ranker).

Like scripts/live_smoke_anthropic.py, this is NOT part of the automated
test suite: it is not under tests/ (pytest's testpaths), never imported
by any test module, and refuses to run under pytest or with an
unconfigured environment. Manual invocation only:

    cd backend
    python scripts/live_smoke_full_pipeline.py

It makes exactly ONE recommendation request (a handful of LLM decision
calls and RecipeAPI.io calls bounded by the orchestrator's own hard
limits -- at most 3 search attempts, 20 evaluated candidates). It never
prints the API keys, the system prompt, or raw provider payloads --
only the safe, high-level diagnostics TECHNICAL_SPEC.md's observability
section allows (request id, attempt/candidate counts, action types,
search anchors, provider route, stop reason, final recipe
ids/names/scores/cost fields).
"""

from __future__ import annotations

import asyncio
import os
import sys

if "PYTEST_CURRENT_TEST" in os.environ:
    raise RuntimeError("live_smoke_full_pipeline.py must never run under pytest")


def _fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


class _CountingLLMProvider:
    provider_name = "anthropic"

    def __init__(self, inner):
        self._inner = inner
        self.call_count = 0
        self.actions_selected: list[str] = []

    async def decide(self, request):
        self.call_count += 1
        response = await self._inner.decide(request)
        self.actions_selected.append(response.raw_action.get("action_type", "<unparsed>"))
        return response


class _CountingRecipeProvider:
    def __init__(self, inner, provider_name: str):
        self._inner = inner
        self.provider_name = provider_name
        self.search_calls: list = []
        self.detail_calls: list[str] = []
        self.recipe_names_by_id: dict[str, str] = {}

    async def search(self, strategy):
        self.search_calls.append(strategy)
        return await self._inner.search(strategy)

    async def get_details(self, provider_recipe_id: str):
        self.detail_calls.append(provider_recipe_id)
        recipe = await self._inner.get_details(provider_recipe_id)
        self.recipe_names_by_id[recipe.id] = recipe.name
        return recipe


async def _run() -> None:
    from app.agent.orchestrator import AgentOrchestrator, AgentRequest
    from app.config import get_settings
    from app.integrations.llm_provider import AnthropicLLMProvider, LLMProviderError
    from app.integrations.recipeapi_io import RecipeAPIIOAdapter
    from app.repositories.price_repository import PriceRepository

    settings = get_settings()
    if not settings.llm_configured:
        _fail("ANTHROPIC_API_KEY / PANTRYPILOT_LLM_MODEL not configured")
    if not settings.recipeapi_io_configured:
        _fail("RECIPEAPI_IO_API_KEY not configured")
    if not os.path.exists(settings.price_db_path):
        _fail(f"reference price DB not found at {settings.price_db_path!r}")

    try:
        llm = _CountingLLMProvider(AnthropicLLMProvider(settings))
        recipeapi = _CountingRecipeProvider(RecipeAPIIOAdapter(settings), "recipeapi_io")
    except LLMProviderError as exc:
        _fail(f"could not construct a provider ({exc.code})")
        return

    price_repository = PriceRepository(settings.price_db_path)
    orchestrator = AgentOrchestrator(llm, {"recipeapi_io": recipeapi}, price_repository)

    # A normal pantry request suitable for RecipeAPI.io, using names
    # confirmed to resolve in the current grocery taxonomy vocabulary.
    request = AgentRequest(
        request_id="live-smoke-full-pipeline-1",
        pantry_raw=["chicken breast", "basmati rice", "onion", "garlic"],
        budget_aed=None,
        cuisine_preference=None,
        cuisine_strict=False,
        servings=4,
        max_total_time_minutes=None,
    )

    try:
        result = await orchestrator.run(request)
    except LLMProviderError as exc:
        _fail(f"live run failed ({exc.code})")
        return
    finally:
        if hasattr(recipeapi, "_inner"):
            await recipeapi._inner.aclose()

    print("PASS: full A-D pipeline completed a live-connected run")
    print(f"  model_used: {settings.pantrypilot_llm_model}")
    print(f"  llm_decision_calls: {llm.call_count}")
    print(f"  actions_selected: {llm.actions_selected}")
    print(f"  search_anchors_by_call: {[s.query_ingredients for s in recipeapi.search_calls]}")
    print(f"  provider_route: recipeapi_io")
    print(f"  search_attempts: {result.search_attempts}")
    print(f"  candidates_detail_fetched: {len(recipeapi.detail_calls)}")
    print(f"  status: {result.status}")
    print(f"  stop_reason: {result.stop_reason}")
    print(f"  progress_events: {result.progress_events}")
    print(f"  final_recommendations: {len(result.recommendations)}")
    for c in result.recommendations:
        print(
            "    - "
            f"recipe_id={c.recipe_id} name={recipeapi.recipe_names_by_id.get(c.recipe_id)!r} "
            f"provider={c.provider} deterministic_score={c.deterministic_score} "
            f"missing_count={c.missing_count} price_complete={c.price_complete} "
            f"estimated_purchase_cost_aed={c.estimated_purchase_cost_aed} "
            f"cost_confidence={c.cost_confidence.value}"
        )
    if not result.recommendations:
        print(f"  closest_alternatives: {len(result.closest_alternatives)}")
        for c in result.closest_alternatives:
            print(f"    - recipe_id={c.recipe_id} rejection_reasons={[r.value for r in c.rejection_reasons]}")


if __name__ == "__main__":
    asyncio.run(_run())
