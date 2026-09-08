"""POST /api/recommend (TECHNICAL_SPEC.md section 15, Module E).

Wires the real, connected pipeline: request validation -> AgentOrchestrator
(Claude Sonnet 5 via AnthropicLLMProvider, DEC-010) -> RecipeAPI.io /
LocalCuratedRecipeProvider -> the unchanged deterministic Module A-C
pipeline -> a user-facing RecommendResponse. Never exposes internal LLM
reasoning, raw provider payloads, or secrets (docs/AGENTS.md).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.agent.orchestrator import AgentOrchestrator, AgentRequest
from app.api.recommend_mapping import build_recommend_response
from app.config import Settings, get_settings
from app.integrations.llm_provider import AnthropicLLMProvider
from app.integrations.local_curated import LocalCuratedRecipeProvider
from app.integrations.recipeapi_io import RecipeAPIIOAdapter
from app.recipe.provider import RecipeProvider
from app.repositories.price_repository import PriceRepository
from app.schemas.recommend import RecommendRequest, RecommendResponse

router = APIRouter()


async def get_recipe_providers(settings: Settings = Depends(get_settings)):
    """Async-generator dependency: the RecipeAPI.io adapter owns an
    httpx.AsyncClient that must be closed after the request, so this
    yields the provider map and closes it in `finally` (FastAPI's
    standard cleanup-dependency pattern) rather than leaking a client
    per request."""

    providers: dict[str, RecipeProvider] = {
        # DEC-012 remains OPEN: the curated dataset ships with zero
        # production records. Registering the (empty) provider still
        # lets the orchestrator route explicit desi requests to it
        # safely -- it simply returns no results rather than erroring.
        "local_curated": LocalCuratedRecipeProvider([]),
    }
    adapter: RecipeAPIIOAdapter | None = None
    if settings.recipeapi_io_configured:
        adapter = RecipeAPIIOAdapter(settings)
        providers["recipeapi_io"] = adapter
    try:
        yield providers
    finally:
        if adapter is not None:
            await adapter.aclose()


def get_price_repository(settings: Settings = Depends(get_settings)) -> PriceRepository:
    return PriceRepository(settings.price_db_path)


def get_llm_provider(settings: Settings = Depends(get_settings)) -> AnthropicLLMProvider:
    return AnthropicLLMProvider(settings)


def get_orchestrator(
    llm_provider: AnthropicLLMProvider = Depends(get_llm_provider),
    recipe_providers: dict[str, RecipeProvider] = Depends(get_recipe_providers),
    price_repository: PriceRepository = Depends(get_price_repository),
) -> AgentOrchestrator:
    return AgentOrchestrator(llm_provider, recipe_providers, price_repository)


@router.post("/recommend", response_model=RecommendResponse)
async def post_recommend(
    request: RecommendRequest,
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
) -> RecommendResponse:
    request_id = f"req_{uuid.uuid4().hex}"

    agent_request = AgentRequest(
        request_id=request_id,
        pantry_raw=request.ingredients,
        budget_aed=request.budget_aed,
        cuisine_preference=request.cuisine,
        cuisine_strict=request.cuisine_strict,
        servings=request.servings,
        max_total_time_minutes=request.max_total_time_minutes,
        excluded_raw=request.excluded_ingredients,
        allow_hard_difficulty=request.allow_hard_difficulty,
    )

    result = await orchestrator.run(agent_request)

    return build_recommend_response(
        result,
        max_total_time_minutes=request.max_total_time_minutes,
        budget_aed=request.budget_aed,
    )
