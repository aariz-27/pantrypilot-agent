"""GET /api/ingredients/suggest (TECHNICAL_SPEC.md section 15, Module E).

Purely a lookup over app.domain.ingredient_autocomplete -- no database
internals exposed, no LLM involvement.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.domain.ingredient_autocomplete import (
    DEFAULT_SUGGESTION_LIMIT,
    MAX_SUGGESTION_LIMIT,
    suggest_ingredients,
)
from app.schemas.ingredients import IngredientSuggestionResponse, IngredientSuggestResponse

router = APIRouter()


@router.get("/ingredients/suggest", response_model=IngredientSuggestResponse)
def get_ingredient_suggestions(
    q: str = Query(min_length=1, max_length=50),
    limit: int = Query(default=DEFAULT_SUGGESTION_LIMIT, ge=1, le=MAX_SUGGESTION_LIMIT),
) -> IngredientSuggestResponse:
    suggestions = suggest_ingredients(q, limit=limit)
    return IngredientSuggestResponse(
        suggestions=[
            IngredientSuggestionResponse(canonical_id=s.canonical_id, display_name=s.display_name)
            for s in suggestions
        ]
    )
