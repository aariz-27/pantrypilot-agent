"""GET /api/ingredients/suggest (TECHNICAL_SPEC.md section 15, Module E).

A lookup over app.domain.ingredient_autocomplete, merged with any
admin-managed canonical ingredients/aliases (runtime integration,
2026-09-13) -- see app.repositories.runtime_ingredient_repository for
the merge/fallback/precedence rules. No database internals exposed, no
LLM involvement.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.config import Settings, get_settings
from app.domain.ingredient_autocomplete import (
    DEFAULT_SUGGESTION_LIMIT,
    MAX_SUGGESTION_LIMIT,
    suggest_ingredients,
)
from app.rate_limit import limiter
from app.repositories.runtime_ingredient_repository import get_merged_vocabulary
from app.schemas.ingredients import IngredientSuggestionResponse, IngredientSuggestResponse

router = APIRouter()


@router.get("/ingredients/suggest", response_model=IngredientSuggestResponse)
@limiter.limit(lambda: get_settings().rate_limit_ingredients_suggest)
def get_ingredient_suggestions(
    request: Request,  # required, by name, for slowapi's @limiter.limit decorator
    q: str = Query(min_length=1, max_length=50),
    limit: int = Query(default=DEFAULT_SUGGESTION_LIMIT, ge=1, le=MAX_SUGGESTION_LIMIT),
    settings: Settings = Depends(get_settings),
) -> IngredientSuggestResponse:
    vocabulary = get_merged_vocabulary(settings.price_db_path)
    suggestions = suggest_ingredients(
        q, limit=limit, canonical_vocabulary=vocabulary.canonical_ids, aliases=vocabulary.aliases
    )
    return IngredientSuggestResponse(
        suggestions=[
            IngredientSuggestionResponse(canonical_id=s.canonical_id, display_name=s.display_name)
            for s in suggestions
        ]
    )
