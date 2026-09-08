// Deterministic, frontend-side recompute for the "I have this" feature
// (ticket section 2, PR #15 review). This module never calls the
// backend/LLM -- it only re-derives pantry match %, matched/missing
// lists, and estimated cost from data the /api/recommend response
// already returned, using the exact same arithmetic the backend uses
// (pantry_coverage = matched / (matched + missing + unresolved); cost
// = sum of remaining missing ingredients' already-known per-ingredient
// costs, never fabricated, never coerced to zero when incomplete).
//
// Only a missing row with a real canonical_id can ever be marked "have"
// -- unresolved/raw rows have canonical_id === null and are never
// promoted into a trusted match through this path (they stay listed as
// unresolved, exactly as the backend left them).

function round2(value) {
  return Math.round(value * 100) / 100
}

// Applies a set of canonical ids the user has confirmed they have to
// one recipe card, moving any matching missing row into "matched" and
// recomputing coverage/cost. Returns the SAME object (referality
// preserved) when nothing on this card is affected, so callers can
// cheaply skip re-rendering unaffected cards.
export function applyExtraPantryToCard(card, extraCanonicalIds) {
  if (!card || !extraCanonicalIds || extraCanonicalIds.size === 0) return card

  const stillMissing = []
  const newlyMatchedNames = []
  for (const row of card.missing_ingredients) {
    if (row.canonical_id && extraCanonicalIds.has(row.canonical_id)) {
      newlyMatchedNames.push(row.display_name)
    } else {
      stillMissing.push(row)
    }
  }

  if (newlyMatchedNames.length === 0) return card

  const matchedSet = new Set(card.matched_ingredients)
  for (const name of newlyMatchedNames) matchedSet.add(name)
  const matched_ingredients = Array.from(matchedSet)

  const totalRequired = card.matched_ingredients.length + card.missing_ingredients.length + card.unresolved_ingredients.length
  const pantry_coverage = totalRequired === 0 ? card.pantry_coverage : matched_ingredients.length / totalRequired

  const allRemainingComplete = stillMissing.every((row) => row.price_complete)
  const estimated_additional_spend_aed = allRemainingComplete
    ? round2(stillMissing.reduce((sum, row) => sum + (row.estimated_cost_aed ?? 0), 0))
    : null

  return {
    ...card,
    matched_ingredients,
    missing_ingredients: stillMissing,
    pantry_coverage,
    price_complete: allRemainingComplete,
    estimated_additional_spend_aed,
  }
}

// Applies the same extra-pantry set across every card in a full
// /api/recommend response (ticket: "update all currently displayed
// recipe cards, not only the card clicked").
export function applyExtraPantryToResponse(response, extraCanonicalIds) {
  if (!response || !extraCanonicalIds || extraCanonicalIds.size === 0) return response
  return {
    ...response,
    recommendations: response.recommendations.map((card) => applyExtraPantryToCard(card, extraCanonicalIds)),
    closest_alternatives: response.closest_alternatives.map((card) => applyExtraPantryToCard(card, extraCanonicalIds)),
  }
}
