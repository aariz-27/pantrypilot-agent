from app.domain.grocery_filtering import is_relevant_product


def test_excluded_product_type_always_filtered_regardless_of_category():
    assert is_relevant_product("Food Cupboard", "Chocolate Bars") is False
    assert is_relevant_product(None, "Energy Drink") is False


def test_approved_category_included_even_with_unrecognized_product_type():
    assert is_relevant_product("Fruits & Vegetables", "Some New Vegetable Type") is True


def test_recognized_ingredient_product_type_included_despite_null_category():
    # LuLu leaves category null for many legitimate fresh fish/meat records.
    assert is_relevant_product(None, "Fresh Fish") is True
    assert is_relevant_product(None, "Whole Chicken") is True
    assert is_relevant_product(None, "Beef Steak") is True


def test_unapproved_category_and_unrecognized_product_type_filtered():
    assert is_relevant_product("Some Unapproved Category", "Some Unknown Type") is False
    assert is_relevant_product(None, None) is False


def test_all_five_approved_categories_pass():
    for category in (
        "Fruits & Vegetables",
        "Fresh Meat & Poultry",
        "Seafood",
        "Dairy , Eggs & Cheese",
        "Food Cupboard",
    ):
        assert is_relevant_product(category, "Unclassified Item") is True
