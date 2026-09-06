"""Shared types for the grocery ingestion/mapping/reference pipeline
(M14/M10 foundation). Deliberately separate from app.domain.models
(the recipe-facing Recipe/RecipeIngredient DTOs) -- grocery ingestion
is a distinct concern with its own provenance and staging needs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MappingStatus(str, Enum):
    MAPPED = "mapped"
    FILTERED_OUT = "filtered_out"
    UNMAPPED_INGREDIENT = "unmapped_ingredient"
    UNPARSEABLE_PRICE = "unparseable_price"
    INVALID_CURRENCY = "invalid_currency"
    UNPARSEABLE_PACKAGE = "unparseable_package"
    UNSUPPORTED_UNIT = "unsupported_unit"
    DUPLICATE = "duplicate"


class PackageBasisSource(str, Enum):
    CONTENT_FIELD = "content_field"
    EXPLICIT_PIECE_COUNT = "explicit_piece_count"


@dataclass(frozen=True)
class RawGroceryRecord:
    """Typed, tolerant view over one raw scraped record. All fields
    except title/price/currency are optional -- the ingestion pipeline
    must tolerate nullable/nonessential source fields."""

    source_name: str
    source_product_id: str | None
    sku: str | None
    title: str
    brand: str | None
    content: str | None
    price_raw: object
    retail_price_raw: object
    discount_amount_raw: object
    discount_ratio_raw: object
    currency_raw: object
    category1: str | None
    category2: str | None
    category3: str | None
    product_type: str | None
    in_stock: bool | None
    product_url: str | None
    scraped_at: str | None


@dataclass(frozen=True)
class ParsedPackage:
    """Result of deterministically parsing a package/content string."""

    package_quantity: float | None
    package_unit: str | None  # raw unit token as parsed, e.g. "kg", "pcs"
    multipack_count: float | None
    normalized_total_quantity: float | None
    normalized_unit: str | None  # controlled: "g" | "ml" | "pcs"
    basis_source: PackageBasisSource | None
    unsupported_unit_token: str | None  # set when the unit is explicitly recognized but not convertible (e.g. "bunch", "gallon")


@dataclass(frozen=True)
class MappedGroceryProduct:
    raw_id: int
    source_name: str
    source_product_id: str | None
    title: str
    brand: str | None
    canonical_id: str | None
    package_quantity: float | None
    package_unit: str | None
    multipack_count: float | None
    normalized_total_quantity: float | None
    normalized_unit: str | None
    current_price_aed: float | None
    normalized_price_per_unit: float | None
    category2: str | None
    product_type: str | None
    mapping_status: MappingStatus
    rejection_reason: str | None
    package_basis_source: PackageBasisSource | None
    product_url: str | None
    scraped_at: str | None


@dataclass(frozen=True)
class ReferencePriceCandidate:
    """One (canonical_id, normalized_unit) contributor used for median
    reference-price computation. package_quantity/package_price_aed/
    normalized_package_quantity are THIS contributor's real,
    actually-purchasable package -- carried through so the CostEngine
    can do real ceil(required/package) purchasing math on a
    representative real product, rather than only a normalized
    per-unit price with no concrete package to buy.
    normalized_package_quantity is the package size already expressed
    in the same base unit as normalized_price_per_unit (e.g. grams),
    so it is directly comparable to a recipe's required quantity."""

    normalized_price_per_unit: float
    package_quantity: float | None
    package_unit: str | None
    package_price_aed: float | None
    normalized_package_quantity: float | None
    source_product_name: str
    source_name: str
    source_url: str | None


@dataclass(frozen=True)
class ReferencePriceResult:
    canonical_id: str
    normalized_unit: str
    normalized_price_per_unit: float
    contributor_count: int
    aggregation_basis: str  # "median_single" | "median_odd" | "median_even"
    source_name: str
    source_product_name: str | None
    source_url: str | None
    # The representative (closest-to-median) contributor's real,
    # purchasable package -- used for ceil(required/package) math.
    package_quantity: float | None = None
    package_unit: str | None = None
    package_price_aed: float | None = None
    normalized_package_quantity: float | None = None


@dataclass(frozen=True)
class IncompatibleUnitGroup:
    """Data-quality signal: a canonical ID whose contributors span more
    than one normalized_unit, so no single reference row is promoted."""

    canonical_id: str
    units_found: tuple[str, ...] = field(default_factory=tuple)
    contributor_count: int = 0
