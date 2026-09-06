"""Deterministic parsing for the grocery ingestion pipeline (M14).

No LLM classification anywhere in this module. Every function either
returns a confident, explicit result or an explicit "unresolved" signal
-- never a guessed value.
"""

from __future__ import annotations

import re

from app.domain.grocery_models import PackageBasisSource, ParsedPackage
from app.domain.grocery_taxonomy import (
    CANONICAL_GROCERY_INGREDIENTS,
    GROCERY_INGREDIENT_ALIASES,
    PRODUCT_TYPE_FIXED_CANONICAL,
    PRODUCT_TYPE_FIXED_CANONICAL_OVERRIDES,
    PRODUCT_TYPE_KEYWORD_RULES,
)
from app.domain.ingredient_normalizer import normalize_ingredient_name

# --- price / currency -----------------------------------------------------


def parse_price(raw_price: object) -> float | None:
    """Never returns 0 or a negative value as a placeholder -- returns
    None (incomplete) instead."""
    if isinstance(raw_price, bool):
        return None
    if isinstance(raw_price, (int, float)):
        value = float(raw_price)
    elif isinstance(raw_price, str):
        cleaned = raw_price.strip().replace(",", "")
        try:
            value = float(cleaned)
        except ValueError:
            return None
    else:
        return None
    if value <= 0:
        return None
    return round(value, 4)


def validate_currency(raw_currency: object, expected: str = "aed") -> bool:
    if not isinstance(raw_currency, str) or not raw_currency.strip():
        return False
    return raw_currency.strip().lower() == expected.lower()


def clean_brand(raw_brand: object) -> str | None:
    """LuLu already supplies a clean, separate brand field -- this only
    trims/normalizes blanks. No brand-from-title extraction is needed
    (or built) for this source; a future source without a clean brand
    field would add its own extraction step ahead of this function
    without changing this module's contract."""
    if isinstance(raw_brand, str) and raw_brand.strip():
        return raw_brand.strip()
    return None


# --- package / content parsing ---------------------------------------------

_MASS_UNITS: dict[str, tuple[str, float]] = {"g": ("g", 1.0), "kg": ("g", 1000.0)}
_VOLUME_UNITS: dict[str, tuple[str, float]] = {
    "ml": ("ml", 1.0),
    "l": ("ml", 1000.0),
    "litre": ("ml", 1000.0),
    "litres": ("ml", 1000.0),
}
_COUNT_UNITS: dict[str, tuple[str, float]] = {"pcs": ("pcs", 1.0), "pc": ("pcs", 1.0)}

_SUPPORTED_UNIT_TOKEN = r"(?:kg|g|ml|litres?|l|pcs?|pc)"

# A range ("1.2 kg-1.5 kg", "(1 kg - 1.3 kg)") is inherently approximate.
# Checked before every other pattern so its first number is never
# silently accepted as if it were exact -- DEC-013/the approved policy
# requires ranges to remain unresolved rather than fabricate precision.
_RANGE_PATTERN = re.compile(
    rf"\d+(?:\.\d+)?\s*{_SUPPORTED_UNIT_TOKEN}\s*-\s*\d+(?:\.\d+)?\s*{_SUPPORTED_UNIT_TOKEN}\b",
    re.IGNORECASE,
)
# An additive bundle ("2 kg + 1 kg", "900 g + 200 g") is an unambiguous
# same-dimension total -- both sides are real, exact numbers, so
# summing them (after normalizing each side) is not a fabrication the
# way accepting only the first number would be.
_ADDITIVE_PATTERN = re.compile(
    rf"(?P<qty1>\d+(?:\.\d+)?)\s*(?P<unit1>{_SUPPORTED_UNIT_TOKEN})\s*\+\s*(?P<qty2>\d+(?:\.\d+)?)\s*(?P<unit2>{_SUPPORTED_UNIT_TOKEN})\b",
    re.IGNORECASE,
)
_MULTIPACK_PATTERN = re.compile(
    rf"(?P<count>\d+(?:\.\d+)?)\s*[x×]\s*(?P<size>\d+(?:\.\d+)?)\s*(?P<unit>{_SUPPORTED_UNIT_TOKEN})\b",
    re.IGNORECASE,
)
_SINGLE_PATTERN = re.compile(
    rf"(?P<qty>\d+(?:\.\d+)?)\s*(?P<unit>{_SUPPORTED_UNIT_TOKEN})\b",
    re.IGNORECASE,
)
_UNSUPPORTED_UNIT_PATTERN = re.compile(
    r"(?P<qty>\d+(?:\.\d+)?)\s*(?P<unit>bunch|pkt|packet|teabags?|gallons?|slices?|pack|box)\b",
    re.IGNORECASE,
)


def _resolve_unit(token: str) -> tuple[str | None, float]:
    token = token.lower()
    if token in _MASS_UNITS:
        return _MASS_UNITS[token]
    if token in _VOLUME_UNITS:
        return _VOLUME_UNITS[token]
    if token in _COUNT_UNITS:
        return _COUNT_UNITS[token]
    return None, 0.0


_EMPTY_PACKAGE = ParsedPackage(
    package_quantity=None,
    package_unit=None,
    multipack_count=None,
    normalized_total_quantity=None,
    normalized_unit=None,
    basis_source=None,
    unsupported_unit_token=None,
)


def parse_package_content(content: object) -> ParsedPackage:
    """Parses TECHNICAL_SPEC/DEC-013-approved formats: "500 g", "1 kg",
    "250 ml", "2 Litres", "4 x 1 Litre", "2 x 200 g", "6 pcs", "30 pcs".

    Explicitly unsupported units (bunch, pkt/packet, teabags, gallon,
    slices, pack, box) are recognized (so callers can classify them
    distinctly from truly unparseable text) but never converted --
    DEC-013 forbids inventing mass/volume conversions for them, and
    forbids silently guessing the gallon standard.

    Two additional real-data cases (independent review finding,
    2026-09-06) are handled explicitly rather than left to the generic
    single-quantity search, which would otherwise silently accept only
    the first number in either case:

    - Ranges ("1.2 kg-1.5 kg", "(1 kg - 1.3 kg) Approx. Weight") are
      always unresolved -- an approximate range is never narrowed to
      one fabricated endpoint.
    - Additive same-dimension bundles ("2 kg + 1 kg", "900 g + 200 g")
      are totaled -- both sides are real, exact numbers, so summing
      them is not a fabrication; a cross-dimension "+" is left
      unresolved rather than guessed.

    Returns an all-None ParsedPackage when nothing reliable is found;
    never guesses a quantity or unit.
    """
    if not isinstance(content, str) or not content.strip():
        return _EMPTY_PACKAGE

    text = content.strip()

    # Checked first: a range is always ambiguous, regardless of what
    # any other pattern might otherwise match within the same string.
    if _RANGE_PATTERN.search(text):
        return _EMPTY_PACKAGE

    additive_match = _ADDITIVE_PATTERN.search(text)
    if additive_match:
        unit1_token = additive_match.group("unit1").lower()
        unit2_token = additive_match.group("unit2").lower()
        normalized_unit1, factor1 = _resolve_unit(unit1_token)
        normalized_unit2, factor2 = _resolve_unit(unit2_token)
        if (
            normalized_unit1 is not None
            and normalized_unit1 == normalized_unit2
        ):
            qty1 = float(additive_match.group("qty1"))
            qty2 = float(additive_match.group("qty2"))
            total_normalized = qty1 * factor1 + qty2 * factor2
            return ParsedPackage(
                package_quantity=None,
                package_unit=None,
                multipack_count=None,
                normalized_total_quantity=round(total_normalized, 4),
                normalized_unit=normalized_unit1,
                basis_source=PackageBasisSource.CONTENT_FIELD,
                unsupported_unit_token=None,
            )
        # Different dimensions on either side of "+" (should not occur
        # for the supported unit set, but defensively): never guess a
        # cross-dimension total -- fall through to remain unresolved.
        return _EMPTY_PACKAGE

    multipack_match = _MULTIPACK_PATTERN.search(text)
    if multipack_match:
        unit_token = multipack_match.group("unit").lower()
        normalized_unit, factor = _resolve_unit(unit_token)
        if normalized_unit is not None:
            count = float(multipack_match.group("count"))
            size = float(multipack_match.group("size"))
            return ParsedPackage(
                package_quantity=size,
                package_unit=unit_token,
                multipack_count=count,
                normalized_total_quantity=round(count * size * factor, 4),
                normalized_unit=normalized_unit,
                basis_source=PackageBasisSource.CONTENT_FIELD,
                unsupported_unit_token=None,
            )

    single_match = _SINGLE_PATTERN.search(text)
    if single_match:
        unit_token = single_match.group("unit").lower()
        normalized_unit, factor = _resolve_unit(unit_token)
        if normalized_unit is not None:
            qty = float(single_match.group("qty"))
            basis = (
                PackageBasisSource.EXPLICIT_PIECE_COUNT
                if normalized_unit == "pcs"
                else PackageBasisSource.CONTENT_FIELD
            )
            return ParsedPackage(
                package_quantity=qty,
                package_unit=unit_token,
                multipack_count=None,
                normalized_total_quantity=round(qty * factor, 4),
                normalized_unit=normalized_unit,
                basis_source=basis,
                unsupported_unit_token=None,
            )

    unsupported_match = _UNSUPPORTED_UNIT_PATTERN.search(text)
    if unsupported_match:
        return ParsedPackage(
            package_quantity=float(unsupported_match.group("qty")),
            package_unit=unsupported_match.group("unit").lower(),
            multipack_count=None,
            normalized_total_quantity=None,
            normalized_unit=None,
            basis_source=None,
            unsupported_unit_token=unsupported_match.group("unit").lower(),
        )

    return _EMPTY_PACKAGE


# --- canonical ingredient resolution ----------------------------------------


def resolve_canonical_id(product_type: object, title: object) -> str | None:
    """Deterministic canonical-ID resolution: productType-driven rules
    first (see app.domain.grocery_taxonomy for the full policy and
    rationale), falling back to the shared M08 normalizer against the
    combined grocery + recipe canonical vocabulary. Returns None
    (UNMAPPED) rather than ever fabricating an ID."""

    product_type_str = product_type if isinstance(product_type, str) else None
    title_str = title if isinstance(title, str) else ""
    title_lower = title_str.lower()

    if product_type_str and product_type_str in PRODUCT_TYPE_FIXED_CANONICAL:
        if product_type_str in PRODUCT_TYPE_FIXED_CANONICAL_OVERRIDES:
            for keyword, canonical_id in PRODUCT_TYPE_FIXED_CANONICAL_OVERRIDES[product_type_str]:
                if keyword in title_lower:
                    return canonical_id
        return PRODUCT_TYPE_FIXED_CANONICAL[product_type_str]

    if product_type_str and product_type_str in PRODUCT_TYPE_KEYWORD_RULES:
        for keyword, canonical_id in PRODUCT_TYPE_KEYWORD_RULES[product_type_str]:
            if keyword in title_lower:
                return canonical_id
        # No default: independent review (2026-09-06) found that
        # guessing the "statistically standard" variant here (e.g.
        # unmatched Fresh Milk -> full_fat_milk) conflicts with DEC-013's
        # "uncertain mappings remain unresolved" rule. Falls through to
        # UNMAPPED_INGREDIENT below rather than any productType-family
        # default.

    if title_lower:
        # Substring alias match against noisy full product titles (titles
        # include brand/descriptor/size noise that normalize_ingredient_name
        # alone -- designed for a single clean ingredient name -- would not
        # cleanly match). Deterministic keyword containment, same technique
        # PRODUCT_TYPE_KEYWORD_RULES already uses above.
        for alias_text, canonical_id in GROCERY_INGREDIENT_ALIASES.items():
            if alias_text in title_lower:
                return canonical_id

    if title_str:
        result = normalize_ingredient_name(
            title_str,
            canonical_vocabulary=CANONICAL_GROCERY_INGREDIENTS,
            aliases=GROCERY_INGREDIENT_ALIASES,
        )
        if result.canonical_id is not None:
            return result.canonical_id

    return None
