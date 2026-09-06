"""LuLu UAE grocery canonical ingredient taxonomy (M10/M14 data).

Built by inspecting the real Founder-provided export
(data/raw/dataset_lulu-scraper_2026-09-06_09-41-43-507.json, 2699
products, 301 distinct `productType` values) -- not invented from
first principles. This is deliberately a separate, larger dataset from
app.domain.canonical_ingredients (PP-001's tiny recipe-normalization
seed fixture, which stays untouched); the two are unified only by both
producing canonical IDs in the same lowercase snake_case namespace.
Where a concept exists in both (e.g. "garlic", "onion"), the same ID is
used intentionally so pantry-matching and price lookup correlate.

Design (per DEC-013 / Founder direction):
- brand never defines identity;
- meaningful cuts/species/forms stay distinct (chicken cuts, beef/lamb
  cuts, fish species) rather than collapsing into a generic bucket;
- marketing terms (premium/fresh/local/value-pack) are not encoded;
- branded prepared spice mixtures (biryani/chicken masala) get their
  own canonical IDs rather than collapsing into component spices.

Coverage is intentionally not exhaustive across all 301 productType
values -- the QA report (scripts/grocery_qa_report.py) surfaces
whatever remains UNMAPPED_INGREDIENT so gaps are visible and can be
closed deliberately (more rules here, or a manual curated entry),
never silently guessed at ingestion time.

Mapping strategy, in order, per product:
1. EXCLUDED_PRODUCT_TYPES -- filtered out before any mapping is
   attempted (finished/snack/candy/beverage/confectionery products;
   these must never pollute the ingredient reference database).
2. PRODUCT_TYPE_FIXED_CANONICAL -- productType alone determines the
   canonical ID unambiguously.
3. PRODUCT_TYPE_KEYWORD_RULES -- productType is a family (e.g. "Fresh
   Milk"); the title's keywords pick the specific canonical ID within
   that family. PRODUCT_TYPE_KEYWORD_DEFAULT supplies a fallback within
   the family when no keyword matches (documented per-case below; this
   picks the statistically standard retail variant, e.g. full-fat milk,
   never a fabricated price/quantity value).
4. Fall through to the shared alias/vocabulary match (title text against
   CANONICAL_GROCERY_INGREDIENTS / GROCERY_INGREDIENT_ALIASES) via the
   same normalize_ingredient_name() PP-001 already provides.
5. Otherwise: UNMAPPED_INGREDIENT.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 1. Excluded product types: finished/snack/candy/beverage/confectionery.
# Never promoted as ingredient reference entries regardless of category.
# ---------------------------------------------------------------------------

EXCLUDED_PRODUCT_TYPES: frozenset[str] = frozenset(
    {
        # snacks / confectionery / biscuits
        "Snacking", "Chocolate Bars", "Chocolate Bags", "Chocolate Coated",
        "Kids Chocolate", "Boxed Chocolate", "Potato Chips", "Corn Chips",
        "Other Crisps", "Crackers", "Rusks", "Cookies", "Plain Biscuits",
        "Cream Filled Biscuits", "Digestive Biscuits", "Kid's Biscuits",
        "Savoury Biscuits", "Pre Pack Cakes", "Cakes & Desserts Ready Mix",
        "Gummy Candies",
        # beverages (ready-to-drink / bottled, not brewing/cooking ingredients)
        "Still Water", "Sparkling Water", "Chilled Juices", "Long Life Juices",
        "Squashes & Cordials", "Malted Drinks", "Carbonated Drinks",
        "Canned Cola", "Bottled Cola", "Tonic & Mixer Drinks", "Energy Drink",
        "Iced Coffee", "Iced Tea",
        # frozen desserts
        "Ice Cream Tubs", "Ice Cream Sticks & Cones", "Ice Cream Bar",
        "Jelly & Pudding", "Custard", "Custard Powder",
        # convenience / ready meals
        "Instant Noodles", "Cup Noodles", "French Fries", "Hash Brown",
        "Other Potato Products", "Wedges", "Burger", "Kofta", "Frozen Kofta",
        "Nuggets", "Zingers", "Samosas", "Puffs", "Meat Balls",
        "Other Ready Meals", "Combo Pack", "Dips Assorted",
        "Filipino Food", "Korean Food", "Mexican Foods", "Sri Lankan Food",
        "Indian Savouries", "Indian Ready Mix & Other Snacking",
        # breakfast cereals (ready-to-eat, distinct from raw Oats which IS an ingredient)
        "Choco Cereals", "Corn Flakes", "Flavored Cereals",
        # supplements / candy-adjacent
        "Protein Bar", "Cereal Bars", "Sports Nutrition", "Healthy Selections",
        "Gums", "Syrups & Frosting",
    }
)

# ---------------------------------------------------------------------------
# 2. Fixed productType -> canonical_id (unambiguous).
# ---------------------------------------------------------------------------

PRODUCT_TYPE_FIXED_CANONICAL: dict[str, str] = {
    # Dairy / cheese / eggs
    "Feta & White Cheese": "feta_cheese",
    "Cheddar Cheese": "cheddar_cheese",
    "Mozzarella & Other Grated Cheese": "mozzarella_cheese",
    "Cheese Slices": "processed_cheese_slices",
    "Cream Cheese & Spreads": "cream_cheese",
    "Laban": "laban",
    "Kefir": "kefir",
    "Plain Yoghurt": "plain_yoghurt",
    "Flavoured Yoghurt": "flavoured_yoghurt",
    "Plain Greek Yoghurt": "greek_yoghurt",
    "Flavoured Greek Yoghurt": "flavoured_greek_yoghurt",
    "Specialized Yoghurt": "specialized_yoghurt",
    "Yoghurt Drink": "yoghurt_drink",
    "Greek Yoghurt Drink": "greek_yoghurt_drink",
    "Flavoured Milk": "flavoured_milk",
    "UHT Milk": "uht_milk",
    "UHT Flavoured Milk": "uht_flavoured_milk",
    "Powdered Milk": "powdered_milk",
    "Evaporated Milk": "evaporated_milk",
    "Sweetened Condensed Milk": "condensed_milk",
    "Coconut Milk": "coconut_milk",
    "Coconut Milk Powder": "coconut_milk_powder",
    "Almond Milk": "almond_milk",
    "Oat Milk": "oat_milk",
    "White Eggs": "egg",
    "Brown Eggs": "egg",
    "Speciality Eggs": "egg",
    "Butter": "butter",
    "Ghee": "ghee",
    "Margarine": "margarine",
    "Cooking Cream": "cooking_cream",
    "Fresh Cream": "fresh_cream",
    "Whipping Cream": "whipping_cream",
    "Flavoured Cream": "flavoured_cream",
    "Coffee Creamer": "coffee_creamer",
    # Meat / poultry
    "Whole Chicken": "whole_chicken",
    "Frozen Whole Chicken": "whole_chicken",
    "Chicken Wings": "chicken_wings",
    "Chicken Drumsticks": "chicken_drumsticks",
    "Chicken Parts": "chicken_parts",
    "Frozen Chicken Portions": "chicken_parts",
    "Minced Chicken": "minced_chicken",
    "Frozen Minced Chicken": "minced_chicken",
    "Marinated Chicken": "marinated_chicken",
    "Poultry Offals": "chicken_offal",
    "Beef Steak": "beef_steak",
    "Minced Beef": "minced_beef",
    "Beef Cubes": "beef_cubes",
    "Beef Roast & Loins": "beef_roast",
    "Lamb & Mutton Minced": "minced_lamb",
    "Lamb Steak": "lamb_steak",
    "Lamb Cubes": "lamb_cubes",
    "Meat Offals": "meat_offal",
    "Canned Luncheon Meat": "canned_luncheon_meat",
    "Canned Corned Beef": "canned_corned_beef",
    "Sausages": "sausages",
    "Frozen Sausages": "sausages",
    # Seafood
    "Squid": "squid",
    "Prawns": "prawns",
    "Frozen Prawns": "prawns",
    "Frozen Shrimps": "shrimp",
    "Crabs": "crab",
    "Canned Tuna": "canned_tuna",
    "Canned Sardines": "canned_sardines",
    # Produce
    "Tomato": "tomato",
    "Onion": "onion",
    "Garlic": "garlic",
    "Capsicum": "bell_pepper",
    "Cucumber": "cucumber",
    "Corns & Baby Corn": "corn",
    "Eggplant": "eggplant",
    "Mushrooms": "mushroom",
    "Beetroot": "beetroot",
    "Sprouts": "sprouts",
    "Chayote": "chayote",
    "Leeks/Spring Onions": "spring_onion",
    "Raddish": "radish",
    "Frozen Green Peas": "green_peas",
    "Frozen Spinach": "spinach",
    "Frozen Molokhia": "molokhia",
    "Frozen Okra": "okra",
    "Frozen Broccoli": "broccoli",
    "Frozen Beans": "green_beans",
    "Grape Leaves": "grape_leaves",
    # Fruits
    "Apples": "apple",
    "Banana": "banana",
    "Green Banana": "green_banana",
    "Grapes": "grapes",
    "Berries": "berries",
    "Mangoes": "mango",
    "Green Mango": "green_mango",
    "Dates": "dates",
    "Fresh Dates": "dates",
    "Avocado": "avocado",
    "Pomegranates": "pomegranate",
    "Kiwi": "kiwi",
    "Pineapple": "pineapple",
    "Papaya": "papaya",
    "Green Papaya": "green_papaya",
    "Guava": "guava",
    "Pears": "pear",
    "Plums": "plum",
    "Nectarine": "nectarine",
    "Peaches": "peach",
    "Apricots": "apricot",
    "Melons": "melon",
    "Jackfruit": "jackfruit",
    # Grains / staples
    "Basmati Rice": "basmati_rice",
    "Egyptian Rice": "egyptian_rice",
    "Jasmine Rice": "jasmine_rice",
    "Sona Masoori": "sona_masoori_rice",
    "Ponni Rice": "ponni_rice",
    "Idli Rice": "idli_rice",
    "Jeerakasala Rice": "jeerakasala_rice",
    "Matta Rice": "matta_rice",
    "White Rice": "white_rice",
    "Pasta": "pasta",
    "Vermicelli": "vermicelli",
    "Oats": "oats",
    # Oils
    "Sunflower Oil": "sunflower_oil",
    "Olive Oil": "olive_oil",
    "Coconut Oil": "coconut_oil",
    "Canola Oil": "canola_oil",
    "Corn Oil": "corn_oil",
    "Blended Oil": "blended_oil",
    # Sugar / baking
    "White Sugar": "white_sugar",
    "Brown Sugar": "brown_sugar",
    "Raw Sugar": "raw_sugar",
    "Icing Sugar": "icing_sugar",
    "Salt": "salt",
    "Baking Soda": "baking_soda",
    "Low Calorie Sweetener": "sugar_substitute",
    # Condiments / preserves
    "Vinegar": "vinegar",
    "Honey": "honey",
    "Ketchup": "ketchup",
    "Mayonnaise": "mayonnaise",
    "Soy Sauce": "soy_sauce",
    "Bouillons": "bouillon",
    "Stock Powder": "stock_powder",
    "Jam": "jam",
    "Peanut Butter": "peanut_butter",
    "Choco Spread": "chocolate_spread",
    "Coconut": "coconut",
    "Cashews": "cashew",
    "Almonds": "almond",
    "Pistachio": "pistachio",
    "Peanuts": "peanut",
    # Canned
    "Canned Tomatoes & Puree": "canned_tomato",
    "Canned Baked Beans": "canned_baked_beans",
    "Canned Beans": "canned_beans",
    "Canned Peas": "canned_peas",
    "Canned Whole Kernel Corn": "canned_corn",
    "Canned Mushroom": "canned_mushroom",
    "Canned Foul Beans": "canned_foul_beans",
    # Frozen dough / pastry (cooking staples, not finished snacks)
    "Frozen Pastry": "frozen_pastry",
    "Frozen Paratha": "frozen_paratha",
}

# ---------------------------------------------------------------------------
# 3. Family productType -> keyword-driven canonical_id.
# Each entry: productType -> (ordered [(keyword, canonical_id), ...], default)
# Keywords are matched case-insensitively as substrings of the title.
# ---------------------------------------------------------------------------

PRODUCT_TYPE_KEYWORD_RULES: dict[str, list[tuple[str, str]]] = {
    "Fresh Milk": [
        ("protein", "protein_milk"),
        ("lactose free", "lactose_free_milk"),
        ("skim", "skimmed_milk"),
        ("low fat", "skimmed_milk"),
        ("full fat", "full_fat_milk"),
        ("full cream", "full_fat_milk"),
    ],
    "Chicken Breasts": [
        ("bone in", "chicken_breast"),
        ("bone-in", "chicken_breast"),
    ],
    "Frozen Chicken Breasts": [
        ("bone in", "chicken_breast"),
        ("bone-in", "chicken_breast"),
    ],
    "Chicken Thighs": [
        ("boneless", "boneless_chicken_thigh"),
    ],
    "Beef Cuts": [
        ("ribeye", "beef_ribeye"),
        ("rib eye", "beef_ribeye"),
        ("sirloin", "beef_sirloin"),
        ("brisket", "beef_brisket"),
        ("shoulder", "beef_shoulder"),
        ("shank", "beef_shank"),
    ],
    "Beef Ribs & Chops": [
        ("rib", "beef_ribs"),
    ],
    "Lamb & Mutton Chops & Cuts": [
        ("cube", "lamb_cubes"),
        ("chop", "lamb_chops"),
        ("leg", "lamb_leg"),
        ("shoulder", "lamb_shoulder"),
    ],
    "Fresh Fish": [
        ("salmon", "whole_salmon"),
        ("sea bass", "whole_sea_bass"),
        ("seabass", "whole_sea_bass"),
        ("tilapia", "whole_tilapia"),
        ("hammour", "whole_hammour"),
        ("kingfish", "whole_kingfish"),
        ("king fish", "whole_kingfish"),
        ("tuna", "whole_tuna"),
        ("scad", "whole_scad"),
        ("mackerel", "whole_mackerel"),
        ("sardine", "whole_sardine"),
    ],
    "Fish Fillet": [
        ("salmon", "salmon_fillet"),
        ("sea bass", "sea_bass_fillet"),
        ("seabass", "sea_bass_fillet"),
        ("tilapia", "tilapia_fillet"),
        ("hammour", "hammour_fillet"),
        ("kingfish", "kingfish_fillet"),
    ],
    "Potatoes & Starchy Vegetables": [
        ("potato", "potato"),
        ("sweet potato", "sweet_potato"),
        ("cassava", "cassava"),
    ],
    "Cabbage & Broccoli": [
        ("broccoli", "broccoli"),
        ("cabbage", "cabbage"),
    ],
    "Leafy Vegetables": [
        ("spinach", "spinach"),
        ("lettuce", "lettuce"),
        ("kale", "kale"),
        ("arugula", "arugula"),
        ("kangkong", "kangkong"),
        ("coriander", "coriander"),
        ("radish leaves", "radish_leaves"),
        ("drumstick", "drumstick_leaves"),
    ],
    "Herbs": [
        ("coriander", "coriander"),
        ("cilantro", "coriander"),
        ("dhania", "coriander"),
        ("mint", "mint"),
        ("parsley", "parsley"),
        ("basil", "basil"),
        ("dill", "dill"),
        ("rosemary", "rosemary"),
        ("thyme", "thyme"),
    ],
    "Courgettes & Artichoke": [
        ("courgette", "zucchini"),
        ("zucchini", "zucchini"),
        ("artichoke", "artichoke"),
    ],
    "Peas & Beans": [
        ("pea", "green_peas"),
        ("bean", "green_beans"),
    ],
    "Citrus Fruits": [
        ("orange", "orange"),
        ("lemon", "lemon"),
        ("lime", "lime"),
        ("grapefruit", "grapefruit"),
    ],
    "Spices": [
        ("turmeric", "turmeric"),
        ("black pepper", "black_pepper"),
        ("cumin", "cumin"),
        ("coriander powder", "coriander_powder"),
        ("mustard seed", "mustard_seed"),
        ("chilli", "chili_powder"),
        ("chili", "chili_powder"),
        ("cinnamon", "cinnamon"),
        ("cardamom", "cardamom"),
        ("clove", "cloves"),
        ("paprika", "paprika"),
    ],
    "Masala": [
        ("biryani", "biryani_masala"),
        ("chicken", "chicken_masala"),
        ("garam", "garam_masala"),
        ("fish", "fish_masala"),
        ("meat", "meat_masala"),
    ],
    "Pulses": [
        ("lentil", "lentils"),
        ("daal", "lentils"),
        ("dal", "lentils"),
        ("chickpea", "chickpeas"),
        ("channa", "chickpeas"),
        ("kidney bean", "kidney_beans"),
        ("rajma", "kidney_beans"),
        ("black gram", "black_gram"),
        ("moong", "moong_dal"),
    ],
    "Flour": [
        ("whole wheat", "whole_wheat_flour"),
        ("atta", "whole_wheat_flour"),
        ("all purpose", "plain_flour"),
        ("plain", "plain_flour"),
        ("rice flour", "rice_flour"),
        ("gram flour", "gram_flour"),
        ("besan", "gram_flour"),
    ],
}

# Default canonical ID used when a family productType's title matches none
# of its keyword rules. Each default is the statistically standard retail
# variant for that family in this market -- a taxonomy/default-naming
# decision, never a fabricated price or package size.
PRODUCT_TYPE_KEYWORD_DEFAULT: dict[str, str] = {
    "Fresh Milk": "full_fat_milk",
    "Chicken Breasts": "boneless_chicken_breast",
    "Frozen Chicken Breasts": "boneless_chicken_breast",
    "Chicken Thighs": "chicken_thigh",
    "Lamb & Mutton Chops & Cuts": "lamb_chops",
    "Cabbage & Broccoli": "cabbage",
    "Courgettes & Artichoke": "zucchini",
    "Peas & Beans": "green_beans",
    "Flour": "plain_flour",
}

# ---------------------------------------------------------------------------
# 4. Additional title-level aliases (Founder-specified regional synonyms),
# consumed the same way as app.domain.canonical_ingredients.INGREDIENT_ALIASES.
# ---------------------------------------------------------------------------

GROCERY_INGREDIENT_ALIASES: dict[str, str] = {
    "coriander": "coriander",
    "cilantro": "coriander",
    "dhania": "coriander",
    "yoghurt": "plain_yoghurt",
    "yogurt": "plain_yoghurt",
    "lady finger": "okra",
    "ladyfinger": "okra",
    "lady fingers": "okra",
    "okra": "okra",
    "bhindi": "okra",
    "capsicum": "bell_pepper",
    "bell pepper": "bell_pepper",
    "atta": "whole_wheat_flour",
    "whole wheat flour": "whole_wheat_flour",
}

# ---------------------------------------------------------------------------
# 5. Full canonical vocabulary: every canonical_id referenced above, plus
# app.domain.canonical_ingredients' set (shared namespace).
# ---------------------------------------------------------------------------

CANONICAL_GROCERY_INGREDIENTS: frozenset[str] = frozenset(
    set(PRODUCT_TYPE_FIXED_CANONICAL.values())
    | {cid for rules in PRODUCT_TYPE_KEYWORD_RULES.values() for _, cid in rules}
    | set(PRODUCT_TYPE_KEYWORD_DEFAULT.values())
    | set(GROCERY_INGREDIENT_ALIASES.values())
)
