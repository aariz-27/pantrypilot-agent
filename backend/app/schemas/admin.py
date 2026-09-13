"""Pydantic request/response models for the admin API (ticket section
21). Never returns raw ORM/sqlite3.Row objects -- every admin route
maps a repository dataclass into one of these explicit models first.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class AdminSessionResponse(BaseModel):
    username: str
    csrf_token: str
    expires_at: str


class CanonicalIngredientResponse(BaseModel):
    canonical_id: str
    display_name: str
    default_unit: str | None
    status: str
    created_at: str
    updated_at: str
    updated_by: str
    alias_count: int
    has_manual_price: bool
    has_reference_price: bool


class CanonicalIngredientListResponse(BaseModel):
    items: list[CanonicalIngredientResponse]
    total: int
    page: int
    page_size: int


class EffectiveIngredientResponse(BaseModel):
    """One row of the EFFECTIVE ingredient catalog (2026-09-13 admin
    completion ticket) -- the built-in app.domain.grocery_taxonomy
    vocabulary and admin-managed canonical_ingredients rows merged into
    one view, exactly as app.repositories.runtime_ingredient_repository.
    get_merged_vocabulary already merges them for the live app. A
    built-in row has no admin-editable metadata (no created_at/
    updated_at/updated_by/default_unit -- it is not a database row),
    so those fields are simply absent here rather than fabricated."""

    canonical_id: str
    display_name: str
    source: str  # "built_in" | "admin"
    status: str
    alias_count: int
    has_manual_price: bool
    has_reference_price: bool


class EffectiveIngredientListResponse(BaseModel):
    items: list[EffectiveIngredientResponse]
    total: int
    page: int
    page_size: int


class CanonicalIngredientCreateRequest(BaseModel):
    canonical_id: str = Field(min_length=2, max_length=64)
    display_name: str = Field(min_length=1, max_length=120)
    default_unit: str | None = Field(default=None, max_length=20)


class CanonicalIngredientUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    default_unit: str | None = Field(default=None, max_length=20)
    status: str | None = Field(default=None, pattern="^(active|archived)$")


class IngredientAliasResponse(BaseModel):
    alias: str
    canonical_id: str
    source: str
    confidence: float
    active: bool
    updated_at: str | None
    updated_by: str | None


class IngredientAliasCreateRequest(BaseModel):
    alias: str = Field(min_length=1, max_length=120)
    source: str = Field(default="manual", max_length=40)


class IngredientAliasReassignRequest(BaseModel):
    new_canonical_id: str = Field(min_length=2, max_length=64)
    confirm_reassignment: bool = Field(
        description="Must be explicitly true. Prevents any accidental silent remap between canonical ingredients."
    )


class ReferencePriceResponse(BaseModel):
    canonical_id: str
    normalized_unit: str
    display_name: str
    normalized_price_per_unit: float
    package_quantity: float | None
    package_unit: str | None
    package_price_aed: float | None
    contributor_count: int
    aggregation_basis: str
    source_name: str
    collected_at: str


class ManualPriceResponse(BaseModel):
    canonical_id: str
    normalized_unit: str
    display_name: str
    normalized_price_per_unit: float
    package_quantity: float | None
    package_unit: str | None
    package_price_aed: float | None
    normalized_package_quantity: float | None
    source_type: str
    provenance_note: str
    collected_at: str
    active: bool
    updated_at: str | None
    updated_by: str | None


class IngredientPricesResponse(BaseModel):
    reference_prices: list[ReferencePriceResponse]
    manual_prices: list[ManualPriceResponse]


class ManualPriceCreateRequest(BaseModel):
    normalized_unit: str = Field(min_length=1, max_length=10)
    display_name: str = Field(min_length=1, max_length=120)
    normalized_price_per_unit: float
    package_quantity: float | None = None
    package_unit: str | None = Field(default=None, max_length=20)
    package_price_aed: float | None = None
    normalized_package_quantity: float | None = None
    provenance_note: str = Field(min_length=1, max_length=500)


class ManualPriceUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    normalized_price_per_unit: float | None = None
    package_quantity: float | None = None
    package_unit: str | None = Field(default=None, max_length=20)
    package_price_aed: float | None = None
    normalized_package_quantity: float | None = None
    provenance_note: str | None = Field(default=None, min_length=1, max_length=500)


class AdminAuditEntryResponse(BaseModel):
    id: int
    occurred_at: str
    admin_username: str
    action: str
    entity_type: str
    entity_id: str
    summary: str
    request_id: str | None


class AdminAuditListResponse(BaseModel):
    items: list[AdminAuditEntryResponse]
    total: int
    page: int
    page_size: int


class AdminDashboardSummaryResponse(BaseModel):
    canonical_ingredient_count: int
    active_alias_count: int
    ingredients_with_manual_price: int
    ingredients_without_known_price: int
    mapped_product_count: int
    unmapped_product_count: int
    effective_ingredient_count: int


class GroceryProductResponse(BaseModel):
    id: int
    title: str
    brand: str | None
    canonical_id: str | None
    mapping_status: str
    rejection_reason: str | None
    normalized_price_per_unit: float | None
    normalized_unit: str | None
    product_type: str | None


class GroceryProductListResponse(BaseModel):
    items: list[GroceryProductResponse]
    total: int
    page: int
    page_size: int
