// Deterministic local re-ranking (Priority 4, PR #15 correction pass,
// 2026-09-08). This is a FAITHFUL PORT of the backend's frozen ranking
// formula (backend/app/domain/ranker.py, TECHNICAL_SPEC.md section 14)
// -- same weights, same cost normalization, same tie-break order. It
// must be kept in sync with that file if the formula ever changes
// (which it must not without a governed decision -- ticket: "Do not
// modify frozen ranking weights").
//
// Why a port instead of a backend call: Priority 4 requires the local
// candidate pool (current top 3 + reserve additional_options) to
// re-rank after an "I have this" confirmation with ZERO Claude/
// RecipeAPI.io calls. The only way to recompute a ranking score
// client-side without a network round trip is to run the identical
// formula locally.
//
// Deliberately NOT ported: rank_candidates' hard_constraint_pass /
// budget-feasibility guards (InvalidInputError paths). Those exist
// server-side to catch a backend construction bug (a candidate
// incorrectly marked feasible). Every card reaching this module already
// passed that guard once, server-side, when the response was first
// built -- re-validating it here would be redundant defense with no
// addressable local failure mode, not a relaxation of the invariant.

export const COVERAGE_WEIGHT = 0.45
export const COST_WEIGHT = 0.3
export const MISSING_WEIGHT = 0.15
export const CUISINE_WEIGHT = 0.1

const INCOMPLETE_COST_SCORE = 0.25

const CONFIDENCE_RANK = { high: 0, medium: 1, low: 2, unknown: 3 }

export function computeMissingScore(missingCount) {
  return 1 - Math.min(missingCount / 5, 1)
}

export function computeCuisineScore(recipeCuisine, preference) {
  if (preference == null || preference === '') return 1.0
  const recipeC = (recipeCuisine ?? '').trim().toLowerCase()
  if (!recipeC) return 0.5
  return recipeC === preference.trim().toLowerCase() ? 1.0 : 0.0
}

function costScoreWithBudget(card, budgetAed) {
  if (!card.price_complete || card.estimated_additional_spend_aed == null) return INCOMPLETE_COST_SCORE
  if (budgetAed === 0) return card.estimated_additional_spend_aed === 0 ? 1.0 : 0.0
  return Math.max(0, 1 - card.estimated_additional_spend_aed / Math.max(budgetAed, 1))
}

function costScoresWithoutBudget(cards) {
  const completeCosts = cards
    .filter((c) => c.price_complete && c.estimated_additional_spend_aed != null)
    .map((c) => c.estimated_additional_spend_aed)
  if (completeCosts.length === 0) return cards.map(() => INCOMPLETE_COST_SCORE)

  const minCost = Math.min(...completeCosts)
  const maxCost = Math.max(...completeCosts)
  return cards.map((c) => {
    if (!c.price_complete || c.estimated_additional_spend_aed == null) return INCOMPLETE_COST_SCORE
    if (maxCost === minCost) return 1.0
    return 1 - (c.estimated_additional_spend_aed - minCost) / (maxCost - minCost)
  })
}

function costForSort(card) {
  return card.price_complete && card.estimated_additional_spend_aed != null ? card.estimated_additional_spend_aed : Infinity
}

// Elementwise tuple comparison, same order rank_candidates' _tie_break_key
// sorts by: score desc, price-complete first, cost-confidence best-first,
// coverage desc, cost asc, missing count asc, name alphabetical.
function compareTieBreak(a, b) {
  const confidenceA = CONFIDENCE_RANK[a.cost_confidence] ?? 3
  const confidenceB = CONFIDENCE_RANK[b.cost_confidence] ?? 3
  const keyA = [
    -(a._localScore ?? 0),
    a.price_complete ? 0 : 1,
    confidenceA,
    -a.pantry_coverage,
    costForSort(a),
    a.missing_ingredients.length,
    (a.name ?? '').toLowerCase(),
  ]
  const keyB = [
    -(b._localScore ?? 0),
    b.price_complete ? 0 : 1,
    confidenceB,
    -b.pantry_coverage,
    costForSort(b),
    b.missing_ingredients.length,
    (b.name ?? '').toLowerCase(),
  ]
  for (let i = 0; i < keyA.length; i++) {
    if (keyA[i] < keyB[i]) return -1
    if (keyA[i] > keyB[i]) return 1
  }
  return 0
}

// Scores and deterministically re-orders a set of already-feasible
// recipe cards using the identical formula/weights as
// backend/app/domain/ranker.py's rank_candidates(). `constraints` is
// {budgetAed, cuisinePreference} -- the SAME user constraints the
// original search used (from the current search form state, not
// re-derived).
export function rerankCards(cards, { budgetAed, cuisinePreference } = {}) {
  if (cards.length === 0) return cards

  const costScores =
    budgetAed == null ? costScoresWithoutBudget(cards) : cards.map((c) => costScoreWithBudget(c, budgetAed))

  const scored = cards.map((card, i) => {
    const missingScore = computeMissingScore(card.missing_ingredients.length)
    const cuisineScore = computeCuisineScore(card.cuisine, cuisinePreference)
    const score =
      COVERAGE_WEIGHT * card.pantry_coverage +
      COST_WEIGHT * costScores[i] +
      MISSING_WEIGHT * missingScore +
      CUISINE_WEIGHT * cuisineScore
    return { ...card, _localScore: score }
  })

  scored.sort(compareTieBreak)
  // eslint-disable-next-line no-unused-vars
  return scored.map(({ _localScore, ...card }) => card)
}
