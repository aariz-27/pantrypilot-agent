"""Category/productType-based relevance filtering (M14).

Deterministic only -- no LLM classification. Keeps irrelevant finished
retail products (energy drinks, candy, chips, ready meals) out of the
ingredient reference database while not over-filtering legitimate
ingredients that happen to carry a null/unexpected category (LuLu's
own export leaves category1/2/3 null for ~150 otherwise-legitimate
fresh fish/meat/produce records).
"""

from __future__ import annotations

from app.domain.grocery_taxonomy import (
    EXCLUDED_PRODUCT_TYPES,
    PRODUCT_TYPE_FIXED_CANONICAL,
    PRODUCT_TYPE_KEYWORD_RULES,
)

# The five Founder-approved source categories, using LuLu's exact
# category2 label text (including its own inconsistent spacing, e.g.
# "Dairy , Eggs & Cheese") -- matched verbatim, not normalized, so a
# genuine label change upstream is visible rather than silently matched.
APPROVED_CATEGORY2: frozenset[str] = frozenset(
    {
        "Fruits & Vegetables",
        "Fresh Meat & Poultry",
        "Seafood",
        "Dairy , Eggs & Cheese",
        "Food Cupboard",
    }
)


def is_relevant_product(category2: object, product_type: object) -> bool:
    """True if this product should be considered for ingredient
    mapping at all. False means FILTERED_OUT before mapping is
    attempted -- never silently priced or promoted."""

    product_type_str = product_type if isinstance(product_type, str) else None

    if product_type_str and product_type_str in EXCLUDED_PRODUCT_TYPES:
        return False

    if product_type_str and (
        product_type_str in PRODUCT_TYPE_FIXED_CANONICAL
        or product_type_str in PRODUCT_TYPE_KEYWORD_RULES
    ):
        # A recognized ingredient productType is relevant regardless of
        # category2 -- LuLu leaves category null for many otherwise
        # legitimate fresh fish/meat/produce records.
        return True

    if isinstance(category2, str) and category2 in APPROVED_CATEGORY2:
        return True

    return False
