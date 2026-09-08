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
   that family, most specific phrase first. There is NO default: a
   family title matching none of its keywords is UNMAPPED_INGREDIENT,
   per DEC-013's "uncertain mappings remain unresolved" rule (a prior
   keyword-default mechanism that guessed the "statistically standard"
   variant was removed after independent review, 2026-09-06).
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
    "Cheddar Cheese": "cheddar_cheese",
    "Cheese Slices": "processed_cheese_slices",
    # NOTE: "Feta & White Cheese", "Mozzarella & Other Grated Cheese", and
    # "Cream Cheese & Spreads" are intentionally NOT fixed-mapped here.
    # Independent review (2026-09-06) found these productType buckets are
    # not reliable single-ingredient signals in the real export -- e.g.
    # "Puck Cream Cheese Spread 300 g" carries productType "Feta & White
    # Cheese", and "Mozzarella & Other Grated Cheese" contains Parmesan,
    # Cheddar, and mixed blends. They are handled as title-keyword-driven
    # families in PRODUCT_TYPE_KEYWORD_RULES below instead, with no
    # default -- an unmatched title in these families is UNMAPPED, never
    # guessed from the productType label alone.
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
    "Carrots": "carrot",
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
# 2b. Fixed-canonical title overrides (final Module C pricing-gap
# resolution, 2026-09-06). A small, narrow, evidence-based exception
# layered on top of PRODUCT_TYPE_FIXED_CANONICAL: unlike
# PRODUCT_TYPE_KEYWORD_RULES (no default -- an unmatched title falls
# through to UNMAPPED), this PRESERVES the fixed-canonical default for
# every title in the productType and only overrides it when a specific,
# real title keyword is present. It never weakens or removes the
# existing default mapping, so it cannot resurrect the "guess when
# uncertain" pattern DEC-013 forbids -- the default here is the
# already-approved fixed mapping, not a guess.
# ---------------------------------------------------------------------------

PRODUCT_TYPE_FIXED_CANONICAL_OVERRIDES: dict[str, list[tuple[str, str]]] = {
    # "Coconut Shredded India 350 g" is a processed, mass-based cooking
    # ingredient with materially different recipe intent from a whole
    # fresh coconut ("Coconut Whole India 1 pc", "King Coconut 1 pc",
    # "Tender Coconut Thailand 1 pc", "Tender Coconut with Opener 1 pc" --
    # all of which correctly stay "coconut", the default).
    "Coconut": [
        ("shredded", "shredded_coconut"),
        ("desiccated", "shredded_coconut"),
    ],
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
        # Real titles state the form explicitly ("Boneless", "Boneless/
        # Skinless", "Fillet", "Cubes", "Bone In") -- each keyword here
        # is real title evidence, not a guess; a title with none of
        # these is correctly UNMAPPED rather than defaulted.
        ("cubes", "chicken_breast_cubes"),
        ("boneless", "boneless_chicken_breast"),
        ("fillet", "boneless_chicken_breast"),
        ("bone in", "chicken_breast"),
        ("bone-in", "chicken_breast"),
    ],
    "Frozen Chicken Breasts": [
        ("cubes", "chicken_breast_cubes"),
        ("boneless", "boneless_chicken_breast"),
        ("fillet", "boneless_chicken_breast"),
        ("bone in", "chicken_breast"),
        ("bone-in", "chicken_breast"),
    ],
    "Chicken Thighs": [
        ("boneless", "boneless_chicken_thigh"),
        ("bone in", "chicken_thigh"),
        ("bone-in", "chicken_thigh"),
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
        # More specific multi-word phrases MUST be checked before the
        # generic "potato" substring they contain (independent review
        # finding, 2026-09-06): "Sweet Potato Egypt 500 g" previously
        # matched generic "potato" first and was wrongly mapped as plain
        # potato.
        ("sweet potato", "sweet_potato"),
        ("cassava", "cassava"),
        ("tapioca", "cassava"),
        ("yam", "yam"),
        ("aravi", "taro"),
        ("potato", "potato"),
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
        # Same ordering bug class as Potatoes & Starchy Vegetables
        # (independent review finding, 2026-09-06): "dal"/"daal" is a
        # substring of "moong dal", "chana dal", "toor dal", "urid dal" --
        # every multi-word specific phrase must be checked before the
        # generic single-word fallback that would otherwise match first
        # and misclassify it (e.g. "LuLu Moong Dal 800 g" wrongly landing
        # on generic lentils instead of moong_dal).
        ("chana dal", "chana_dal"),
        ("toor dal", "toor_dal"),
        ("tur dal", "toor_dal"),
        ("moong dal", "moong_dal"),
        ("urid dal", "urad_dal"),
        ("urad dal", "urad_dal"),
        ("masoor", "lentils"),
        ("kidney bean", "kidney_beans"),
        ("rajma", "kidney_beans"),
        ("black eye", "black_eyed_peas"),
        ("green pea", "green_peas"),
        ("chana", "chickpeas"),
        ("channa", "chickpeas"),
        ("chic pea", "chickpeas"),
        ("chickpea", "chickpeas"),
        ("toor", "toor_dal"),
        ("urid", "urad_dal"),
        ("urad", "urad_dal"),
        ("moong", "mung_bean"),
        ("dal", "lentils"),
        ("daal", "lentils"),
        ("lentil", "lentils"),
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
    # The following cheese productType families are independent-review
    # findings (2026-09-06): LuLu's own category labels ("Feta & White
    # Cheese", "Mozzarella & OTHER Grated Cheese") are themselves
    # heterogeneous store-aisle groupings, not reliable single-ingredient
    # signals -- real examples include "Puck Cream Cheese Spread 300 g"
    # filed under "Feta & White Cheese", and Parmesan/Cheddar/Emmental
    # filed under "Mozzarella & Other Grated Cheese". Every entry here is
    # title-keyword-driven with NO default -- an unmatched title is
    # UNMAPPED, never guessed from the productType label alone.
    "Feta & White Cheese": [
        ("halloumi", "halloumi_cheese"),
        ("cream cheese", "cream_cheese"),
        ("cottage cheese", "cottage_cheese"),
        ("mascarpone", "mascarpone_cheese"),
        ("brie", "brie_cheese"),
        ("camembert", "camembert_cheese"),
        ("kashkaval", "kashkaval_cheese"),
        ("kashkawan", "kashkaval_cheese"),
        ("ricotta", "ricotta_cheese"),
        ("akkawi", "akkawi_cheese"),
        ("akawi", "akkawi_cheese"),
        ("paneer", "paneer"),
        ("burrata", "burrata_cheese"),
        ("romano", "romano_cheese"),
        ("feta", "feta_cheese"),
        ("white cheese", "white_cheese"),
    ],
    "Mozzarella & Other Grated Cheese": [
        ("mozzarella", "mozzarella_cheese"),
        ("parmesan", "parmesan_cheese"),
        ("romano", "romano_cheese"),
        ("emmental", "emmental_cheese"),
        ("cheddar", "cheddar_cheese"),
        ("4 cheese", "mixed_shredded_cheese"),
        ("four cheese", "mixed_shredded_cheese"),
        ("mexican cheese", "mixed_shredded_cheese"),
        ("cheese blend", "mixed_shredded_cheese"),
        ("cheese mix", "mixed_shredded_cheese"),
    ],
    "Cream Cheese & Spreads": [
        ("cheddar", "cheddar_cheese"),
        ("cream cheese", "cream_cheese"),
        ("white cheese", "white_cheese"),
        ("cheez", "cream_cheese"),
        ("cheeze", "cream_cheese"),
    ],
    "Speciality Cheese": [
        ("labneh", "labneh"),
        ("halloumi", "halloumi_cheese"),
        ("gouda", "gouda_cheese"),
        ("kashkaval", "kashkaval_cheese"),
        ("kashkawan", "kashkaval_cheese"),
        ("grana padano", "parmesan_cheese"),
        ("parmesan", "parmesan_cheese"),
        ("brie", "brie_cheese"),
        ("gruyere", "gruyere_cheese"),
        ("blue cheese", "blue_cheese"),
        ("string cheese", "string_cheese"),
        ("roumy", "roumy_cheese"),
        # "Moutabal" (an eggplant dip) genuinely appears under this
        # productType in the real export -- intentionally no rule for
        # it, so it correctly falls through to UNMAPPED rather than
        # being counted as a cheese.
    ],
}

# NOTE: a PRODUCT_TYPE_KEYWORD_DEFAULT ("guess the standard retail
# variant when no keyword matches") previously existed here and was
# removed per independent review (2026-09-06): defaulting e.g. unmatched
# "Fresh Milk" titles to full_fat_milk, or unmatched "Flour" titles to
# plain_flour, conflicts with DEC-013's "uncertain mappings remain
# unresolved" rule. A family productType whose title matches none of its
# PRODUCT_TYPE_KEYWORD_RULES now falls through to UNMAPPED_INGREDIENT --
# never a guessed canonical ID.

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
    # PR #15 second correction pass (2026-09-08): found live during
    # multi-anchor validation -- RecipeAPI.io ingredient text and the
    # ticket's own pantry example both use the US term "ground beef",
    # which has no path to the existing "minced_beef" canonical id
    # (only the UK term "Minced Beef" was an exact vocabulary match).
    # Same US/UK synonym gap as coriander/cilantro above, not a new
    # concept.
    "ground beef": "minced_beef",
    # PR #15 sixth correction pass (2026-09-08): found live during the
    # lamb-family provider audit -- RecipeAPI.io's real ingredient text
    # is "Ground lamb" (61 real recipes confirmed live), which has no
    # path to the existing "minced_lamb" canonical id (only "Minced
    # lamb" was an exact vocabulary match). Same US/UK synonym gap as
    # ground beef/minced_beef above.
    "ground lamb": "minced_lamb",
}

# ---------------------------------------------------------------------------
# 4b. Canonical grocery ingredients that are recognized identities in this
# taxonomy but are NOT (yet) produced by any LuLu ingestion mapping rule
# above. Their reference price comes solely from the DEC-013 manual
# curated fallback (backend/data/manual/manual_price_entries.json),
# reviewed by the Founder, per the essential-ingredient price-coverage
# audit (2026-09-06).
#
# Adding an ID here does NOT change ingestion/mapping behavior: it is not
# referenced by PRODUCT_TYPE_FIXED_CANONICAL or PRODUCT_TYPE_KEYWORD_RULES,
# and it does not add a new GROCERY_INGREDIENT_ALIASES substring rule, so
# re-running the LuLu ingestion pipeline against the same real dataset
# produces byte-identical mapping/QA results to before this addition.
#
# - "ginger": genuinely present in the real LuLu export (e.g. "Ginger
#   India 200 g") but under productType "Chillies & Spicy", which has no
#   keyword-family rule in this ticket's scope -- taxonomy-unmapped from
#   LuLu today, closed via manual fallback instead.
# - "salted_butter" / "unsalted_butter": the real export's "Butter"
#   productType contains both salted and unsalted titles, but productType
#   "Butter" remains fixed-mapped to generic "butter" unchanged (Founder
#   decision: do not repurpose or re-split generic "butter" in this
#   ticket). Distinct pricing for salted/unsalted is intentionally
#   manual-only for now.
# ---------------------------------------------------------------------------

MANUAL_ONLY_CANONICAL_INGREDIENTS: frozenset[str] = frozenset(
    {
        "ginger",
        "salted_butter",
        "unsalted_butter",
    }
)

# ---------------------------------------------------------------------------
# 4c. Reference-price-eligibility exclusions (essential-ingredient
# data-quality fix, 2026-09-06). Narrow, evidence-based exceptions where
# a real LuLu contributor legitimately carries a canonical_id but its
# unit is categorically incompatible with that ingredient's normal
# mass/volume form -- so it must never enter reference-price
# aggregation for that canonical_id, even though it remains a genuine
# `mapped` row in mapped_grocery_products (nothing is silently dropped
# from ingestion or from ingredient identity; only excluded from *that
# canonical_id's* reference-price candidate pool). Never a blanket
# per-unit rule and never applied globally -- always scoped to one
# specific canonical_id and justified by a specific real title.
#
# - "butter" excludes "ml": the sole ml contributor is "Lurpak Butter
#   Roasting Spray 200 ml" -- a cooking spray, not a normal mass-based
#   butter package. No salted/unsalted/block/portion butter title in the
#   real export is ml-based, so this cannot exclude any of them. No
#   density conversion is performed; the spray row simply never
#   contributes to the "butter" reference-price statistic.
# - "apple" excludes "pcs": the sole pcs contributor is "Rockit Apple 1
#   pkt 5 pcs". Converting a piece count to grams would require
#   inventing an average apple weight, which DEC-013 forbids. Every
#   other real "Apples" productType title in the export is kg/g-based.
#
# Final Module C pricing-gap resolution (2026-09-06) -- the remaining 9
# incompatible-unit groups were each individually inspected (every real
# contributor row, grouped by unit, titles/prices/package content
# reviewed). Two of the nine (corn, mayonnaise) had NO non-arbitrary
# deterministic signal available -- see the code comment above the
# `RESIDUAL_INCOMPATIBLE_CANONICAL_IDS` note near the bottom of this
# file for why they are intentionally left unresolved rather than
# forced. The other seven were resolved as follows:
#
# - "evaporated_milk" excludes "ml": the sole ml contributor is "Rainbow
#   Original Evaporated Milk Portion 10 x 14 ml" -- a single-serve
#   creamer-style portion pack, a genuinely different consumption form
#   from the four g-based standard cans (170 g/410 g), which is the
#   normal cooking-ingredient form.
# - "flavoured_yoghurt" excludes "ml" and "pcs":
#   - the sole ml contributor, "Unikai Meethi Lassi 190 ml", is a
#     drinkable lassi, not a spoonable yoghurt -- genuinely different
#     recipe intent from the 42 g-based spoonable cups/pots.
#   - the two pcs contributors ("Al Rawabi Blackberry & Raspberry
#     Yoghurt 1 pc", "Al Rawabi Fruit Yoghurt Assorted 6 pcs") are
#     ordinary spoonable pot yoghurts whose LuLu listing simply omits a
#     weight in the content field -- a packaging/source-data anomaly,
#     not a different product. Converting piece count to grams would
#     require inventing a per-cup weight, which DEC-013 forbids, so they
#     are excluded rather than guessed.
# - "fresh_cream" excludes "ml": the three ml contributors ("El mlea
#   Double Cream 270 ml", "El mlea Single Cream 270 ml", "President
#   Light Cooking Cream 200 ml") are pourable liquid creams, a
#   genuinely different physical form from the ten g-based thick
#   tub/soured-cream products (Al Rawabi, Almarai, Daisy, Marmum -- all
#   weight-labeled). Notably, "President Light Cooking Cream" conceptually
#   duplicates the taxonomy's own separate "Cooking Cream" productType/
#   canonical_id ("cooking_cream") -- LuLu's own "Fresh Cream" productType
#   label is inconsistent for this title; a future ticket could
#   reclassify it via a title-keyword override (as done here for
#   "shredded_coconut"), but that is not required to give "fresh_cream"
#   itself a safe, correct reference price, so it is left as a disclosed
#   follow-up rather than done here.
# - "ghee" excludes "g": unlike the other exclusions, this is NOT a
#   "different product form" case -- ghee is genuinely, legitimately
#   sold both by weight (5 contributors, e.g. "Almarai Pure Butter Ghee
#   800 g") and by volume (15 contributors) in the real export, with no
#   title-level distinguishing signal between them (same product,
#   different brand packaging choices). Volume is chosen as ghee's
#   canonical reference-price basis NOT because it has more
#   contributors (an explicitly forbidden justification), but for
#   architectural consistency with every other pure cooking fat/oil
#   already in this taxonomy -- sunflower_oil, olive_oil, coconut_oil,
#   canola_oil, and corn_oil are all priced in ml, and ghee is used
#   identically in recipes (poured/measured by volume).
# - "ketchup" excludes "ml": the sole ml contributor, "Heinz Less Sugar
#   and Salt Tomato Ketchup 400 ml", is the same brand/product family as
#   6 other Heinz ketchup SKUs that are all g-labeled (342 g/369 g/
#   400 g/460 g/570 g/910 g) -- an isolated retailer/source labeling
#   inconsistency for this one SKU, not a genuinely different product
#   form, and ketchup density cannot be safely assumed to make a g/ml
#   conversion.
# - "whipping_cream" excludes "g": both g contributors are explicitly
#   pre-made/aerosol products -- "Puck Whipping Cream Spray 250 g" (a
#   spray, the same contaminant pattern as the butter case) and "Baskin
#   Robbins Whipped Light Cream 425 g" (a ready-whipped topping) --
#   genuinely different from the ten ml contributors, which are all raw
#   pourable liquid cream meant to be whipped as part of a recipe.
#
# This dict is intentionally NOT consulted by resolve_canonical_id() --
# mapping/classification is unaffected; only run_normalization()'s
# reference-price candidate grouping (scripts/normalize_grocery_prices.py)
# and the QA report's incompatible-group accounting consult it.
# ---------------------------------------------------------------------------

REFERENCE_PRICE_EXCLUDED_UNITS: dict[str, frozenset[str]] = {
    "butter": frozenset({"ml"}),
    "apple": frozenset({"pcs"}),
    "evaporated_milk": frozenset({"ml"}),
    "flavoured_yoghurt": frozenset({"ml", "pcs"}),
    "fresh_cream": frozenset({"ml"}),
    "ghee": frozenset({"g"}),
    "ketchup": frozenset({"ml"}),
    "whipping_cream": frozenset({"g"}),
}

# ---------------------------------------------------------------------------
# 4d. Residual, intentionally unresolved incompatible-unit groups (final
# Module C pricing-gap resolution, 2026-09-06). "corn" (1 g contributor,
# "Sweet Corn Big 1 kg", vs 1 pcs contributor, "Sweet Corn 2 pcs") and
# "mayonnaise" (2 g contributors vs 4 ml contributors, split across
# multiple different brands with no title-level distinguishing signal
# and no cross-taxonomy consistency argument analogous to ghee's) both
# lack any non-arbitrary deterministic basis to prefer one unit over the
# other -- picking one would violate the explicit "never choose the
# majority unit just because it is the majority" rule with no
# independent justification available. Neither is in the approved
# essential-ingredient checklist. Left unresolved rather than forced;
# recommended path is a Founder-reviewed manual curated fallback entry
# if either is needed before Module D.
# ---------------------------------------------------------------------------

RESIDUAL_INCOMPATIBLE_CANONICAL_IDS: frozenset[str] = frozenset({"corn", "mayonnaise"})

# ---------------------------------------------------------------------------
# 5. Full canonical vocabulary: every canonical_id referenced above, plus
# app.domain.canonical_ingredients' set (shared namespace).
# ---------------------------------------------------------------------------

CANONICAL_GROCERY_INGREDIENTS: frozenset[str] = frozenset(
    set(PRODUCT_TYPE_FIXED_CANONICAL.values())
    | {cid for rules in PRODUCT_TYPE_KEYWORD_RULES.values() for _, cid in rules}
    | {cid for rules in PRODUCT_TYPE_FIXED_CANONICAL_OVERRIDES.values() for _, cid in rules}
    | set(GROCERY_INGREDIENT_ALIASES.values())
    | MANUAL_ONLY_CANONICAL_INGREDIENTS
)
