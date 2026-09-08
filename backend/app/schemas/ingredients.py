from __future__ import annotations

from pydantic import BaseModel


class IngredientSuggestionResponse(BaseModel):
    canonical_id: str
    display_name: str


class IngredientSuggestResponse(BaseModel):
    suggestions: list[IngredientSuggestionResponse]
