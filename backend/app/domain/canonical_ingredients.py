"""Seed canonical ingredient vocabulary and alias table.

This is a small foundation seed set sufficient to make ingredient
normalization functional and testable in this ticket. It is NOT the
final production ingredient/alias dataset -- that is populated from the
real grocery data ingestion pipeline (M14) and is out of scope here
(the price repository and cost engine are explicitly excluded from this
ticket). Canonical IDs are lowercase snake_case per docs/AGENTS.md.
"""

from __future__ import annotations

CANONICAL_INGREDIENTS: frozenset[str] = frozenset(
    {
        "chicken_breast",
        "rice",
        "onion",
        "garlic",
        "soy_sauce",
        "egg",
        "bread",
        "cheese",
        "beef",
        "potato",
        "tomato",
        "lentils",
        "pasta",
        "flour",
        "sugar",
        "oil",
        "yogurt",
        "bell_pepper",
        "ginger",
        "butter",
        # Distinct from generic "butter": recipes may explicitly require
        # one or the other, and substituting between them is never done
        # silently (Founder decision, essential-ingredient audit).
        "salted_butter",
        "unsalted_butter",
        "milk",
        "salt",
        "black_pepper",
        "cumin",
        "coriander",
        "turmeric",
        "chili",
        "lemon",
        "spinach",
        "carrot",
    }
)

# Non-food requirements that must not be silently priced or counted
# toward pantry food coverage (TECHNICAL_SPEC.md section 12).
OTHER_REQUIREMENT_IDS: frozenset[str] = frozenset(
    {
        "kitchen_twine",
        "toothpick",
        "skewer",
        "parchment_paper",
        "aluminum_foil",
    }
)

# alias (already unicode-normalized/lowercased/trimmed) -> canonical_id
INGREDIENT_ALIASES: dict[str, str] = {
    "capsicum": "bell_pepper",
    "bell peppers": "bell_pepper",
    "green pepper": "bell_pepper",
    "chicken breasts": "chicken_breast",
    "boneless chicken breast": "chicken_breast",
    "chicken fillet": "chicken_breast",
    "spring onion": "onion",
    "red onion": "onion",
    "onions": "onion",
    "garlic clove": "garlic",
    "garlic cloves": "garlic",
    "cloves garlic": "garlic",
    "tomatoes": "tomato",
    "potatoes": "potato",
    "eggs": "egg",
    "lentil": "lentils",
    "daal": "lentils",
    "dal": "lentils",
    "cooking oil": "oil",
    "vegetable oil": "oil",
    "olive oil": "oil",
    "curd": "yogurt",
    "plain yogurt": "yogurt",
    "green chili": "chili",
    "green chilies": "chili",
    "red chili": "chili",
    "chillies": "chili",
    "chilli": "chili",
    "black pepper": "black_pepper",
    "ground black pepper": "black_pepper",
    "coriander leaves": "coriander",
    "cilantro": "coriander",
    "kitchen string": "kitchen_twine",
    "butcher's twine": "kitchen_twine",
}
