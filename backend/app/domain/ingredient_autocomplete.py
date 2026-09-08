"""Module E: deterministic ingredient autocomplete (ticket section 28).

Purely a lookup over the already-approved canonical grocery taxonomy
and its aliases (app.domain.grocery_taxonomy) -- the same taxonomy
app.agent.orchestrator normalizes pantry input against, so a suggestion
accepted here is guaranteed to resolve identically at recommendation
time. Never calls the LLM. Never returns or implies a suggestion for
text that is not already an approved canonical ingredient or alias.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.grocery_taxonomy import CANONICAL_GROCERY_INGREDIENTS, GROCERY_INGREDIENT_ALIASES

DEFAULT_SUGGESTION_LIMIT = 10
MAX_SUGGESTION_LIMIT = 20


@dataclass(frozen=True)
class IngredientSuggestion:
    canonical_id: str
    display_name: str


def humanize_canonical_id(canonical_id: str) -> str:
    """Deterministic display formatting only -- never invents new
    identity, just title-cases the already-approved canonical_id."""
    return canonical_id.replace("_", " ").strip().title()


def _display_names() -> dict[str, str]:
    return {cid: humanize_canonical_id(cid) for cid in CANONICAL_GROCERY_INGREDIENTS}


def suggest_ingredients(query: str, limit: int = DEFAULT_SUGGESTION_LIMIT) -> list[IngredientSuggestion]:
    """Bounded, display-friendly, alias-aware canonical ingredient
    suggestions for the given free-text query prefix/substring.

    Ranking: exact display-name match first, then display-name-starts-
    with-query, then substring match anywhere (in the display name or
    any alias text pointing at that canonical id), then alphabetical --
    entirely deterministic, no ranking "score" is exposed.
    """

    cleaned = query.strip().lower()
    bounded_limit = max(1, min(limit, MAX_SUGGESTION_LIMIT))
    if not cleaned:
        return []

    display_by_id = _display_names()

    # alias text (already lowercased in GROCERY_INGREDIENT_ALIASES) that
    # matches, grouped by the canonical id it resolves to.
    alias_hits: dict[str, str] = {}
    for alias_text, canonical_id in GROCERY_INGREDIENT_ALIASES.items():
        if cleaned in alias_text and canonical_id not in alias_hits:
            alias_hits[canonical_id] = alias_text

    candidates: dict[str, tuple[int, str]] = {}  # canonical_id -> (rank, sort_key)
    for canonical_id, display_name in display_by_id.items():
        lower_display = display_name.lower()
        if lower_display == cleaned:
            rank = 0
        elif lower_display.startswith(cleaned):
            rank = 1
        elif cleaned in lower_display:
            rank = 2
        elif canonical_id in alias_hits:
            rank = 3
        else:
            continue
        candidates[canonical_id] = (rank, display_name)

    ordered = sorted(candidates.items(), key=lambda item: (item[1][0], item[1][1]))
    return [
        IngredientSuggestion(canonical_id=cid, display_name=display_by_id[cid])
        for cid, _ in ordered[:bounded_limit]
    ]
