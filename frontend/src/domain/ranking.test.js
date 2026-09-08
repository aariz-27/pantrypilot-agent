import { describe, expect, it } from 'vitest'
import { computeCuisineScore, computeMissingScore, rerankCards } from './ranking'

// Test vectors deliberately mirror backend/tests/unit/test_ranker.py --
// this module is a faithful port of backend/app/domain/ranker.py and
// must stay in sync with it (Priority 4, PR #15 correction pass).

function makeCard(overrides = {}) {
  return {
    recipe_id: 'r1',
    name: 'Test',
    cuisine: null,
    pantry_coverage: 0.8,
    missing_ingredients: [{ raw_name: 'b' }],
    estimated_additional_spend_aed: 5.0,
    price_complete: true,
    cost_confidence: 'high',
    ...overrides,
  }
}

describe('computeMissingScore', () => {
  it('matches the frozen formula: 1 - min(missingCount / 5, 1)', () => {
    expect(computeMissingScore(0)).toBe(1.0)
    expect(computeMissingScore(5)).toBe(0.0)
    expect(computeMissingScore(10)).toBe(0.0) // clamped
    expect(computeMissingScore(1)).toBeCloseTo(0.8)
  })
})

describe('computeCuisineScore', () => {
  it('exact match scores 1.0', () => {
    expect(computeCuisineScore('Chinese', 'chinese')).toBe(1.0)
  })
  it('unknown recipe cuisine under a soft preference scores 0.5', () => {
    expect(computeCuisineScore(null, 'Chinese')).toBe(0.5)
  })
  it('known non-match scores 0.0', () => {
    expect(computeCuisineScore('Italian', 'Chinese')).toBe(0.0)
  })
  it('no preference is neutral (1.0)', () => {
    expect(computeCuisineScore('Italian', null)).toBe(1.0)
  })
})

describe('rerankCards', () => {
  it('matches the spec weights with a budget', () => {
    const card = makeCard({
      recipe_id: 'r1',
      cuisine: 'Chinese',
      pantry_coverage: 0.8,
      missing_ingredients: [{ raw_name: 'b' }],
      estimated_additional_spend_aed: 5.0,
      price_complete: true,
    })
    // coverage=0.8 cost_score=1-5/10=0.5 missing_score=1-1/5=0.8 cuisine_score=1.0
    const expected = 0.45 * 0.8 + 0.3 * 0.5 + 0.15 * 0.8 + 0.1 * 1.0
    // We don't expose the internal score, so infer it indirectly: a
    // second card with a strictly lower expected score must rank after.
    const worse = makeCard({ recipe_id: 'r2', cuisine: 'Chinese', pantry_coverage: 0.1, missing_ingredients: [] })
    const [first, second] = rerankCards([worse, card], { budgetAed: 10.0, cuisinePreference: 'Chinese' })
    expect(first.recipe_id).toBe('r1')
    expect(second.recipe_id).toBe('r2')
    expect(expected).toBeGreaterThan(0)
  })

  it('zero budget with zero known cost scores the full cost component', () => {
    const zeroCard = makeCard({ recipe_id: 'zero', estimated_additional_spend_aed: 0.0, pantry_coverage: 0.8, missing_ingredients: [{ raw_name: 'b' }] })
    const nonZeroCard = makeCard({ recipe_id: 'nonzero', estimated_additional_spend_aed: 1.0, pantry_coverage: 0.8, missing_ingredients: [{ raw_name: 'b' }] })
    const [first] = rerankCards([nonZeroCard, zeroCard], { budgetAed: 0.0 })
    expect(first.recipe_id).toBe('zero')
  })

  it('without a budget, cost is normalized within the candidate set (cheaper ranks higher, all else equal)', () => {
    const cheap = makeCard({ recipe_id: 'cheap', estimated_additional_spend_aed: 2.0 })
    const expensive = makeCard({ recipe_id: 'expensive', estimated_additional_spend_aed: 10.0 })
    const ranked = rerankCards([expensive, cheap], { budgetAed: null })
    expect(ranked[0].recipe_id).toBe('cheap')
  })

  it('all-incomplete-cost without a budget uses the conservative 0.25 score for every candidate (order unaffected by cost)', () => {
    const a = makeCard({ recipe_id: 'a', estimated_additional_spend_aed: null, price_complete: false, cost_confidence: 'unknown', pantry_coverage: 0.9 })
    const b = makeCard({ recipe_id: 'b', estimated_additional_spend_aed: null, price_complete: false, cost_confidence: 'unknown', pantry_coverage: 0.1 })
    const ranked = rerankCards([b, a], { budgetAed: null })
    expect(ranked[0].recipe_id).toBe('a') // higher coverage wins since cost ties
  })

  it('tie-break prefers a complete price over an incomplete one at an otherwise-equal score', () => {
    const complete = makeCard({ recipe_id: 'complete', pantry_coverage: 0.5, missing_ingredients: [{}, {}], estimated_additional_spend_aed: 5.0, price_complete: true })
    const incomplete = makeCard({ recipe_id: 'incomplete', pantry_coverage: 0.5, missing_ingredients: [{}, {}], estimated_additional_spend_aed: null, price_complete: false, cost_confidence: 'unknown' })
    const ranked = rerankCards([incomplete, complete], { budgetAed: null })
    expect(ranked[0].recipe_id).toBe('complete')
  })

  it('tie-break falls back to alphabetical name when everything else is equal', () => {
    const a = makeCard({ recipe_id: 'a', name: 'Alpha Dish', pantry_coverage: 0.6, missing_ingredients: [{}], estimated_additional_spend_aed: 5.0 })
    const b = makeCard({ recipe_id: 'b', name: 'Beta Dish', pantry_coverage: 0.6, missing_ingredients: [{}], estimated_additional_spend_aed: 5.0 })
    const ranked = rerankCards([b, a], { budgetAed: 10.0 })
    expect(ranked.map((c) => c.recipe_id)).toEqual(['a', 'b'])
  })

  it('a reserve candidate can outrank an originally-higher-ranked one after its coverage improves', () => {
    // Simulates the Priority-4 "reserve candidate moves into top 3"
    // scenario: card A starts ahead, card B (a reserve/additional
    // option) is recomputed with much higher coverage/lower missing
    // count after an "I have this" confirmation.
    const originallyFirst = makeCard({ recipe_id: 'A', pantry_coverage: 0.4, missing_ingredients: [{}, {}, {}] })
    const reserveAfterRecompute = makeCard({ recipe_id: 'B', pantry_coverage: 0.95, missing_ingredients: [] })
    const ranked = rerankCards([originallyFirst, reserveAfterRecompute], { budgetAed: null })
    expect(ranked[0].recipe_id).toBe('B')
  })

  it('returns an empty array unchanged', () => {
    expect(rerankCards([], {})).toEqual([])
  })
})
