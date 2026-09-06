import pytest

from app.db.connection import connection_scope
from app.db.schema import create_schema
from app.domain.constraint_evaluator import evaluate_constraints
from app.domain.cost_engine import estimate_ingredient_cost, estimate_purchase_cost
from app.domain.models import CostConfidence, NormalizationStatus, Recipe, RecipeIngredient, RejectionReason, UserConstraints
from app.repositories.price_repository import PriceRepository


@pytest.fixture()
def db_path(tmp_path):
    path = str(tmp_path / "test_cost.db")
    with connection_scope(path, read_only=False) as connection:
        create_schema(connection)
        # tomato: 20 AED per 1000 g package -> 0.02 AED/g
        connection.execute(
            """
            INSERT INTO ingredient_prices (
                canonical_id, normalized_unit, display_name, normalized_price_per_unit,
                package_quantity, package_unit, package_price_aed, normalized_package_quantity,
                contributor_count, aggregation_basis, source_name, source_product_name,
                source_url, collected_at
            ) VALUES ('tomato', 'g', 'tomato', 0.02, 1000, 'g', 20.0, 1000, 1, 'median_single',
                      'lulu_uae', 'Tomato 1 kg', 'https://example.test/tomato', '2026-09-06')
            """
        )
        # egg: 15 AED per 30 pcs
        connection.execute(
            """
            INSERT INTO ingredient_prices (
                canonical_id, normalized_unit, display_name, normalized_price_per_unit,
                package_quantity, package_unit, package_price_aed, normalized_package_quantity,
                contributor_count, aggregation_basis, source_name, source_product_name,
                source_url, collected_at
            ) VALUES ('egg', 'pcs', 'egg', 0.5, 30, 'pcs', 15.0, 30, 1, 'median_single',
                      'lulu_uae', 'White Eggs 30 pcs', 'https://example.test/egg', '2026-09-06')
            """
        )
        connection.commit()
    return path


def ingredient(raw_name, canonical_id, raw_measure=None):
    return RecipeIngredient(
        raw_name=raw_name,
        canonical_id=canonical_id,
        raw_measure=raw_measure,
        normalization_status=NormalizationStatus.EXACT if canonical_id else NormalizationStatus.UNKNOWN,
    )


# --- single ingredient cost ---------------------------------------------------


def test_one_package_sufficient(db_path):
    repo = PriceRepository(db_path)
    ing = ingredient("tomato", "tomato", raw_measure="500 g")
    result = estimate_ingredient_cost(ing, repo)
    assert result.packages_needed == 1
    assert result.line_cost_aed == 20.0
    assert result.price_complete is True
    assert result.cost_confidence == CostConfidence.HIGH


def test_multiple_packages_needed(db_path):
    repo = PriceRepository(db_path)
    ing = ingredient("tomato", "tomato", raw_measure="1500 g")
    result = estimate_ingredient_cost(ing, repo)
    assert result.packages_needed == 2  # ceil(1500/1000)
    assert result.line_cost_aed == 40.0


def test_exact_boundary_does_not_round_up_unnecessarily(db_path):
    repo = PriceRepository(db_path)
    ing = ingredient("tomato", "tomato", raw_measure="1000 g")
    result = estimate_ingredient_cost(ing, repo)
    assert result.packages_needed == 1
    assert result.line_cost_aed == 20.0


def test_missing_price_is_incomplete_never_zero(db_path):
    repo = PriceRepository(db_path)
    ing = ingredient("saffron", "saffron", raw_measure="1 g")
    result = estimate_ingredient_cost(ing, repo)
    assert result.price_complete is False
    assert result.line_cost_aed is None
    assert result.cost_confidence == CostConfidence.UNKNOWN


def test_ambiguous_measure_uses_conservative_one_package(db_path):
    repo = PriceRepository(db_path)
    ing = ingredient("tomato", "tomato", raw_measure="a pinch")
    result = estimate_ingredient_cost(ing, repo)
    assert result.packages_needed == 1
    assert result.line_cost_aed == 20.0
    assert result.price_complete is True
    assert result.cost_confidence == CostConfidence.MEDIUM  # approximate, not exact


def test_no_measure_at_all_uses_conservative_one_package(db_path):
    repo = PriceRepository(db_path)
    ing = ingredient("tomato", "tomato", raw_measure=None)
    result = estimate_ingredient_cost(ing, repo)
    assert result.packages_needed == 1
    assert result.cost_confidence == CostConfidence.MEDIUM


def test_incompatible_unit_dimension_falls_back_conservatively_not_fabricated(db_path):
    repo = PriceRepository(db_path)
    # tomato is priced per gram; requesting "2 pcs" is a different dimension.
    ing = ingredient("tomato", "tomato", raw_measure="2 pcs")
    result = estimate_ingredient_cost(ing, repo)
    assert result.packages_needed == 1
    assert result.cost_confidence == CostConfidence.MEDIUM
    assert result.line_cost_aed == 20.0  # one whole package, never a density/dimension conversion


def test_unknown_canonical_id_is_incomplete(db_path):
    repo = PriceRepository(db_path)
    ing = ingredient("mystery item", None, raw_measure="1 g")
    result = estimate_ingredient_cost(ing, repo)
    assert result.price_complete is False
    assert result.canonical_id is None


# --- aggregate purchase cost ---------------------------------------------------


def test_aggregate_cost_sums_multiple_missing_ingredients(db_path):
    repo = PriceRepository(db_path)
    missing = [ingredient("tomato", "tomato", "500 g"), ingredient("egg", "egg", "30 pcs")]
    result = estimate_purchase_cost(missing, repo)
    assert result.price_complete is True
    assert result.estimated_purchase_cost_aed == pytest.approx(20.0 + 15.0)


def test_aggregate_cost_incomplete_if_any_ingredient_incomplete(db_path):
    repo = PriceRepository(db_path)
    missing = [ingredient("tomato", "tomato", "500 g"), ingredient("saffron", "saffron", "1 g")]
    result = estimate_purchase_cost(missing, repo)
    assert result.price_complete is False
    assert result.estimated_purchase_cost_aed is None  # never a partial sum, never zero


def test_aggregate_cost_no_missing_ingredients_is_zero_and_complete(db_path):
    repo = PriceRepository(db_path)
    result = estimate_purchase_cost([], repo)
    assert result.price_complete is True
    assert result.estimated_purchase_cost_aed == 0.0


def test_pantry_present_ingredients_are_not_this_module_concern(db_path):
    # This module never decides what's missing -- that's
    # app.domain.pantry_matcher's job, unchanged. Only ingredients the
    # caller has already determined are missing should be passed in.
    repo = PriceRepository(db_path)
    # Passing zero ingredients (as if everything were pantry-present)
    # correctly yields a complete, zero-cost result.
    result = estimate_purchase_cost([], repo)
    assert result.estimated_purchase_cost_aed == 0.0


# --- integration with frozen PP-001 constraint evaluator -----------------------


def make_recipe(**overrides):
    defaults = dict(
        id="lulu_test:1", provider="lulu_test", provider_recipe_id="1", name="Test Recipe",
        ingredients=[RecipeIngredient(raw_name="tomato", canonical_id="tomato")],
        instructions="Cook it.",
    )
    defaults.update(overrides)
    return Recipe(**defaults)


def test_budget_pass_with_complete_cost(db_path):
    repo = PriceRepository(db_path)
    cost = estimate_purchase_cost([ingredient("tomato", "tomato", "500 g")], repo)
    result = evaluate_constraints(make_recipe(), UserConstraints(budget_aed=25.0), cost)
    assert result.hard_constraint_pass is True


def test_budget_fail_with_complete_cost(db_path):
    repo = PriceRepository(db_path)
    cost = estimate_purchase_cost([ingredient("tomato", "tomato", "2500 g")], repo)  # ceil(2500/1000)=3 packages = 60 AED
    result = evaluate_constraints(make_recipe(), UserConstraints(budget_aed=25.0), cost)
    assert result.hard_constraint_pass is False
    assert RejectionReason.BUDGET_EXCEEDED in result.rejection_reasons


def test_budget_with_incomplete_cost_is_indeterminate_under_frozen_contract(db_path):
    repo = PriceRepository(db_path)
    cost = estimate_purchase_cost([ingredient("saffron", "saffron", "1 g")], repo)
    result = evaluate_constraints(make_recipe(), UserConstraints(budget_aed=25.0), cost)
    assert result.hard_constraint_pass is False
    assert RejectionReason.BUDGET_INDETERMINATE_COST_INCOMPLETE in result.rejection_reasons
    assert cost.estimated_purchase_cost_aed is None
