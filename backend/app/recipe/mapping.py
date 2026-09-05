"""Shared provider-to-domain mapping helpers (M07 foundation).

Deliberately minimal: only the identity/provenance guard that is
genuinely identical across every provider lives here. Field-shape
mapping (RecipeAPI.io's JSON vs. a curated record's shape) stays in
each adapter, since inventing one generic mapper for two very
different raw shapes would be over-engineering for two providers.

"Usable" at this layer means only: the recipe has enough identity to
be safely constructed as a Recipe DTO (non-blank provider,
provider_recipe_id, name). Deeper usability (has instructions, has a
non-empty ingredient list) is intentionally left to the existing
constraint evaluator (PP-001, app.domain.constraint_evaluator), which
already implements INSTRUCTIONS_UNUSABLE / INGREDIENT_LIST_UNUSABLE /
PROVENANCE_INVALID checks. This ticket must not duplicate that logic.
"""

from __future__ import annotations

from app.domain.provider_errors import RecipeProviderMalformedResponseError


def build_recipe_id(provider: str, provider_recipe_id: str) -> str:
    return f"{provider}:{provider_recipe_id}"


def require_usable_identity(
    *,
    provider: str,
    provider_recipe_id: str | None,
    name: str | None,
    source_description: str,
) -> tuple[str, str]:
    """Validate the minimum identity fields needed to construct a
    trustworthy Recipe DTO. Returns (provider_recipe_id, name) as
    cleaned strings on success. Raises RecipeProviderMalformedResponseError
    on failure -- this recipe cannot be mapped, and must not be
    fabricated a placeholder identity."""

    cleaned_id = str(provider_recipe_id).strip() if provider_recipe_id is not None else ""
    cleaned_name = name.strip() if isinstance(name, str) else ""

    if not cleaned_id or not cleaned_name:
        raise RecipeProviderMalformedResponseError(
            f"{source_description} is missing a usable recipe id or name "
            f"(provider={provider!r}, provider_recipe_id={provider_recipe_id!r}, name={name!r})"
        )

    return cleaned_id, cleaned_name
