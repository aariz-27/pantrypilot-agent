"""LocalCuratedRecipeProvider foundation (M06).

Approved read-only regional gap-filler for explicit Indian/Pakistani/
desi requests (DEC-003). DEC-012 (final curated dataset size/content)
remains OPEN -- this module implements only the provider class and a
deterministic, storage-agnostic loading/mapping mechanism. It ships
with zero bundled recipe data; a caller supplies records via the
constructor. This lets the real curated dataset (once DEC-012 is
resolved) plug in later without redesigning this class, and avoids
bulk-inventing curated content in this ticket. Do not add production
recipe data here.

Storage is intentionally NOT SQLite. PP-001 excluded the SQLite
reference database (no DB infrastructure exists yet in this codebase),
and building SQLite loading now would invent database schema/migration
machinery this ticket does not need. A future ticket can add a
SQLite-backed loader that produces the same CuratedRecordInput records
this provider already accepts, without changing this contract.

Read-only: no create/update/delete methods exist here. No admin UI, no
bulk import system, per DEC-003.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.domain.models import NormalizationStatus, Recipe, RecipeIngredient
from app.domain.provider_errors import RecipeNotFoundError
from app.recipe.mapping import build_recipe_id, require_usable_identity
from app.recipe.provider import SearchResult, SearchResultItem, SearchStrategy, dedupe_search_results


@dataclass(frozen=True)
class CuratedIngredientInput:
    raw_name: str
    quantity: float | None = None
    unit: str | None = None
    optional: bool = False
    # A curator may already know the canonical ingredient ID for a
    # manually authored recipe. This code never invents one -- it only
    # ever passes through what the caller supplies.
    canonical_id: str | None = None


@dataclass(frozen=True)
class CuratedRecordInput:
    """One curated recipe record, in the shape this provider expects to
    receive it. Provenance fields are mandatory per DEC-003 /
    TECHNICAL_SPEC.md section 10: "every curated recipe must have
    explicit provenance"."""

    recipe_id: str
    name: str
    cuisine: str
    source_label: str
    provenance_note: str
    ingredients: list[CuratedIngredientInput] = field(default_factory=list)
    instructions: str | None = None
    source_url: str | None = None
    image_url: str | None = None
    servings: int | None = None
    prep_time_minutes: int | None = None
    cook_time_minutes: int | None = None
    is_active: bool = True

    def __post_init__(self) -> None:
        if not self.source_label.strip() or not self.provenance_note.strip():
            raise ValueError(
                f"Curated record {self.recipe_id!r} is missing mandatory "
                "source_label/provenance_note (DEC-003)"
            )


class LocalCuratedRecipeProvider:
    """Read-only RecipeProvider for approved Indian/Pakistani/desi
    coverage gaps. Implements the RecipeProvider Protocol structurally
    (see app.recipe.provider.RecipeProvider)."""

    provider_name = "local_curated"

    def __init__(self, records: list[CuratedRecordInput]) -> None:
        # Duplicate authoritative records must fail visibly rather than
        # silently coexist (docs/DATA_INTEGRITY_POLICY.md section 17).
        seen_ids: set[str] = set()
        for record in records:
            if record.recipe_id in seen_ids:
                raise ValueError(f"Duplicate curated recipe_id supplied: {record.recipe_id!r}")
            seen_ids.add(record.recipe_id)

        # Only active records are ever visible through this provider.
        # This class never deletes a record; deactivation/versioning is
        # a data-management concern for whichever ticket owns the real
        # dataset, not this runtime read path.
        self._records_by_id: dict[str, CuratedRecordInput] = {
            record.recipe_id: record for record in records if record.is_active
        }

    async def search(self, strategy: SearchStrategy) -> SearchResult:
        requested_cuisine = strategy.cuisine.strip().lower() if strategy.cuisine else None
        requested_ingredients = {i.strip().lower() for i in strategy.query_ingredients if i.strip()}

        items: list[SearchResultItem] = []
        for record in self._records_by_id.values():
            if requested_cuisine and record.cuisine.strip().lower() != requested_cuisine:
                continue
            if requested_ingredients:
                record_ingredient_names = {ing.raw_name.strip().lower() for ing in record.ingredients}
                if not requested_ingredients & record_ingredient_names:
                    continue
            items.append(
                SearchResultItem(
                    id=build_recipe_id(self.provider_name, record.recipe_id),
                    provider=self.provider_name,
                    provider_recipe_id=record.recipe_id,
                    name=record.name,
                    image_url=record.image_url,
                    cuisine=record.cuisine,
                )
            )

        items = dedupe_search_results(items)

        # Small local, in-memory dataset: paginate the already-filtered
        # list deterministically rather than issuing any external call.
        page_size = strategy.page_size
        start = (strategy.page - 1) * page_size
        page_items = items[start : start + page_size]
        has_more = start + page_size < len(items)

        return SearchResult(items=page_items, page=strategy.page, page_size=page_size, has_more=has_more)

    async def get_details(self, provider_recipe_id: str) -> Recipe:
        record = self._records_by_id.get(provider_recipe_id)
        if record is None:
            raise RecipeNotFoundError(f"No active local curated recipe with id {provider_recipe_id!r}")
        return self._map_recipe(record)

    def _map_recipe(self, record: CuratedRecordInput) -> Recipe:
        recipe_recipe_id, name = require_usable_identity(
            provider=self.provider_name,
            provider_recipe_id=record.recipe_id,
            name=record.name,
            source_description="Local curated recipe record",
        )

        ingredients = [
            RecipeIngredient(
                raw_name=ing.raw_name,
                canonical_id=ing.canonical_id,
                raw_measure=(
                    f"{ing.quantity} {ing.unit}".strip()
                    if ing.quantity is not None and ing.unit
                    else ing.unit
                ),
                quantity=ing.quantity,
                normalized_unit=None,
                optional=ing.optional,
                normalization_status=(
                    NormalizationStatus.EXACT if ing.canonical_id else NormalizationStatus.UNKNOWN
                ),
            )
            for ing in record.ingredients
        ]

        return Recipe(
            id=build_recipe_id(self.provider_name, recipe_recipe_id),
            provider=self.provider_name,
            provider_recipe_id=recipe_recipe_id,
            name=name,
            cuisine=record.cuisine,
            category=None,
            image_url=record.image_url,
            ingredients=ingredients,
            instructions=record.instructions,
            source_url=record.source_url,
            servings=record.servings,
            prep_time_minutes=record.prep_time_minutes,
            cook_time_minutes=record.cook_time_minutes,
            fetched_at=datetime.now(timezone.utc),
            source_label=record.source_label,
            provenance_note=record.provenance_note,
        )
