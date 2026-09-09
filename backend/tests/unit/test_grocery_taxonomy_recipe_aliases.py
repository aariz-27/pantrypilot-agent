"""Regression tests for the PR #15 yellow/Uncertain audit implementation
(2026-09-09): Part 1 (approved safe aliases), Part 2 (restored dropped
Module-A aliases), and Part 3 (non-food OTHER_REQUIREMENT_IDS wiring).

Every case here was verified live against the audit's actual observed
data before being added -- see the audit report. This file locks in
exactly the approved, narrow set; it is not a general fuzz test.
"""

from __future__ import annotations

import pytest

from app.domain.grocery_parsing import resolve_canonical_id
from app.domain.grocery_taxonomy import (
    CANONICAL_GROCERY_INGREDIENTS,
    GROCERY_INGREDIENT_ALIASES,
    OTHER_REQUIREMENT_IDS,
    RECIPE_INGREDIENT_ALIASES,
)
from app.domain.ingredient_normalizer import normalize_ingredient_name

# --- Part 1: approved, observed-live safe aliases ---------------------------

PART_1_SAFE_ALIASES = [
    ("parmesan", "parmesan_cheese"),
    ("mozzarella", "mozzarella_cheese"),
    ("ricotta", "ricotta_cheese"),
    ("fettuccine pasta", "pasta"),
    ("small pasta", "pasta"),
    ("ziti pasta", "pasta"),
    ("penne pasta", "pasta"),
    ("pasta shell", "pasta"),
    ("green bell pepper", "bell_pepper"),
    ("red onion", "onion"),
    ("scallion", "spring_onion"),
    ("cinnamon stick", "cinnamon"),
    ("cardamom pod", "cardamom"),
    ("cumin seed", "cumin"),
    ("black peppercorn", "black_pepper"),
    ("turmeric powder", "turmeric"),
]


@pytest.mark.parametrize("raw,expected_canonical", PART_1_SAFE_ALIASES)
def test_part1_approved_safe_alias_resolves(raw, expected_canonical):
    result = normalize_ingredient_name(raw, CANONICAL_GROCERY_INGREDIENTS, GROCERY_INGREDIENT_ALIASES)
    assert result.canonical_id == expected_canonical


# --- Part 1: deliberate recipe-normalization CONVENTIONS (flour/sugar) ------
# Scoped to RECIPE_INGREDIENT_ALIASES only -- see test_flour_sugar_do_not_
# leak_into_grocery_ingestion below for why these must NOT be in the
# shared GROCERY_INGREDIENT_ALIASES dict.


def test_bare_flour_resolves_to_plain_flour_for_recipe_normalization():
    result = normalize_ingredient_name("flour", CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES)
    assert result.canonical_id == "plain_flour"


def test_bare_sugar_resolves_to_white_sugar_for_recipe_normalization():
    result = normalize_ingredient_name("sugar", CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES)
    assert result.canonical_id == "white_sugar"


def test_more_specific_flour_and_sugar_variants_unaffected_by_the_convention():
    # A recipe stating a more specific variant must keep resolving to its
    # own distinct, already-existing canonical id -- the bare-word
    # convention must never override a more specific match.
    assert (
        normalize_ingredient_name("whole wheat flour", CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES).canonical_id
        == "whole_wheat_flour"
    )
    assert (
        normalize_ingredient_name("brown sugar", CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES).canonical_id
        == "brown_sugar"
    )


def test_flour_and_sugar_conventions_do_not_leak_into_grocery_ingestion():
    """Regression for a real defect found while implementing this ticket:
    merging "flour"->plain_flour / "sugar"->white_sugar into the SHARED
    GROCERY_INGREDIENT_ALIASES dict silently defeated
    grocery_parsing.resolve_canonical_id's deliberate "no default" rule
    (DEC-013) for the "Flour"/"Sugar" PRODUCT_TYPE_KEYWORD_RULES/
    PRODUCT_TYPE_FIXED_CANONICAL families -- almost any real product
    title in those families contains the bare substring. An ambiguous
    real grocery product title with no more specific keyword must stay
    UNMAPPED_INGREDIENT during ingestion, exactly as before this ticket."""

    assert resolve_canonical_id("Flour", "Some Brand Flour 1 kg") is None
    assert "flour" not in GROCERY_INGREDIENT_ALIASES
    assert "sugar" not in GROCERY_INGREDIENT_ALIASES
    # The convention is still reachable for recipe/pantry text, just not
    # for grocery ingestion, via the separate RECIPE_INGREDIENT_ALIASES dict.
    assert RECIPE_INGREDIENT_ALIASES["flour"] == "plain_flour"
    assert RECIPE_INGREDIENT_ALIASES["sugar"] == "white_sugar"


# --- Part 2: restored dropped Module-A aliases ------------------------------

PART_2_RESTORED_ALIASES = [
    ("garlic clove", "garlic"),
    ("garlic cloves", "garlic"),
    ("cloves garlic", "garlic"),
    ("green pepper", "bell_pepper"),
    ("ground black pepper", "black_pepper"),
    ("coriander leaves", "coriander"),
]


@pytest.mark.parametrize("raw,expected_canonical", PART_2_RESTORED_ALIASES)
def test_part2_restored_dropped_alias_resolves(raw, expected_canonical):
    result = normalize_ingredient_name(raw, CANONICAL_GROCERY_INGREDIENTS, GROCERY_INGREDIENT_ALIASES)
    assert result.canonical_id == expected_canonical


def test_stale_dropped_aliases_were_deliberately_not_restored():
    """Documents the Part 2 judgment calls: these old Module-A aliases
    were reviewed and NOT restored because their old target is now
    either stale (a more specific canonical id already exists, so
    restoring the old generic target would be a specificity regression)
    or nonexistent in the production taxonomy."""

    # "chicken fillet"/"boneless chicken breast" -> chicken_breast (old):
    # PRODUCT_TYPE_KEYWORD_RULES' "fillet" -> boneless_chicken_breast rule
    # is ingestion-only (grocery_parsing.resolve_canonical_id), never
    # consulted by normalize_ingredient_name -- so "chicken fillet" stays
    # genuinely unresolved for recipe text today. Restoring the OLD
    # alias's generic "chicken_breast" target would still be a
    # specificity regression relative to the more precise
    # "boneless_chicken_breast" id this taxonomy already has for exactly
    # this concept, so it was deliberately left unrestored rather than
    # restored to a less-specific target.
    assert (
        normalize_ingredient_name("chicken fillet", CANONICAL_GROCERY_INGREDIENTS, GROCERY_INGREDIENT_ALIASES).canonical_id
        is None
    )
    # "spring onion" -> onion (old): spring_onion is its own distinct,
    # already-existing canonical id; restoring the old alias would
    # collapse it into generic onion.
    assert (
        normalize_ingredient_name("spring onion", CANONICAL_GROCERY_INGREDIENTS, GROCERY_INGREDIENT_ALIASES).canonical_id
        == "spring_onion"
    )
    # "dal"/"daal" -> lentils (old): held back on specificity grounds
    # (dal can mean a specific pulse variety) -- must remain unresolved.
    assert normalize_ingredient_name("dal", CANONICAL_GROCERY_INGREDIENTS, GROCERY_INGREDIENT_ALIASES).canonical_id is None
    assert normalize_ingredient_name("daal", CANONICAL_GROCERY_INGREDIENTS, GROCERY_INGREDIENT_ALIASES).canonical_id is None
    # "cooking oil"/"vegetable oil"/"curd" -> targets that no longer
    # exist in the production taxonomy at all -- must remain unresolved
    # (REVIEW NEEDED items, out of scope for the original PR #15 audit-
    # implementation pass). "milk" remains a deliberately untouched
    # Priority-3 "ambiguous mapping" item per the later controlled
    # canonical + pricing expansion pass (2026-09-09) -- still correctly
    # unresolved. NOTE: "green chili", "tomato paste", and "celery" were
    # ALSO asserted unresolved here originally, but that later pass
    # deliberately added them as their own new, distinct, priced
    # canonicals (green_chili, tomato_paste, celery) -- see
    # test_review_needed_expansion.py for their current, correct
    # resolution behavior.
    for raw in ("cooking oil", "vegetable oil", "curd", "milk"):
        assert (
            normalize_ingredient_name(raw, CANONICAL_GROCERY_INGREDIENTS, GROCERY_INGREDIENT_ALIASES).canonical_id is None
        ), f"{raw!r} is a REVIEW NEEDED item and must not have been aliased in this pass"


def test_must_remain_uncertain_items_still_unresolved():
    """Part 5: genuinely ambiguous items must still be rejected -- no
    unsafe mapping was added for any of these in this pass."""

    for raw in ("rice", "pepper", "firm white fish", "water"):
        assert (
            normalize_ingredient_name(raw, CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES).canonical_id is None
        ), f"{raw!r} must remain Uncertain -- no safe canonical target exists"


# --- Part 3: non-food OTHER_REQUIREMENT_IDS wiring --------------------------

NON_FOOD_RAW_TEXT_CASES = [
    ("parchment paper", "parchment_paper"),
    ("cedar plank", "cedar_plank"),
    ("kitchen twine", "kitchen_twine"),
    ("kitchen string", "kitchen_twine"),
    ("butcher's twine", "kitchen_twine"),  # cleans to "butcher s twine" (apostrophe -> space)
    ("aluminum foil", "aluminum_foil"),
    ("aluminium foil", "aluminum_foil"),
    ("tin foil", "aluminum_foil"),
    ("skewer", "skewer"),
    ("skewers", "skewer"),
    ("toothpick", "toothpick"),
    ("toothpicks", "toothpick"),
]


@pytest.mark.parametrize("raw,expected_canonical", NON_FOOD_RAW_TEXT_CASES)
def test_non_food_requirement_text_now_resolves(raw, expected_canonical):
    """Before this fix, none of these resolved at all (OTHER_REQUIREMENT_IDS
    lived only in the disconnected app.domain.canonical_ingredients module,
    never reachable from real recipe-ingredient normalization) -- they fell
    through to UNKNOWN/Uncertain exactly like a genuine taxonomy gap."""

    result = normalize_ingredient_name(raw, CANONICAL_GROCERY_INGREDIENTS, GROCERY_INGREDIENT_ALIASES)
    assert result.canonical_id == expected_canonical
    assert result.canonical_id in OTHER_REQUIREMENT_IDS


def test_other_requirement_ids_do_not_leak_into_grocery_ingestion_as_food():
    # These non-food ids must never be reachable as a grocery reference-
    # price ingestion outcome -- no PRODUCT_TYPE_FIXED_CANONICAL/
    # PRODUCT_TYPE_KEYWORD_RULES entry produces any of them (they are
    # recipe-side classification only, added via section 4e/6 of
    # grocery_taxonomy.py, never via the ingestion-mapping tables).
    from app.domain.grocery_taxonomy import PRODUCT_TYPE_FIXED_CANONICAL, PRODUCT_TYPE_KEYWORD_RULES

    ingestion_produced_ids = set(PRODUCT_TYPE_FIXED_CANONICAL.values()) | {
        cid for rules in PRODUCT_TYPE_KEYWORD_RULES.values() for _, cid in rules
    }
    assert ingestion_produced_ids.isdisjoint(OTHER_REQUIREMENT_IDS)
