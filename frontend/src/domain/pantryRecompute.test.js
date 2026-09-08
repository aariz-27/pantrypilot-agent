import { describe, expect, it } from 'vitest'
import { applyExtraPantryToCard, applyExtraPantryToResponse } from './pantryRecompute'

function makeCard(overrides = {}) {
  return {
    recipe_id: 'recipeapi_io:1',
    matched_ingredients: ['Chicken Breast'],
    missing_ingredients: [
      { raw_name: 'onion', canonical_id: 'onion', display_name: 'Onion', estimated_cost_aed: 2.5, price_complete: true },
      { raw_name: 'garlic', canonical_id: 'garlic', display_name: 'Garlic', estimated_cost_aed: 1.5, price_complete: true },
    ],
    unresolved_ingredients: ['Some weird sauce'],
    pantry_coverage: 1 / 4,
    price_complete: true,
    estimated_additional_spend_aed: 4.0,
    ...overrides,
  }
}

describe('applyExtraPantryToCard', () => {
  it('returns the same object reference when nothing on the card is affected', () => {
    const card = makeCard()
    const result = applyExtraPantryToCard(card, new Set(['tomato']))
    expect(result).toBe(card)
  })

  it('moves a matching missing ingredient into matched and recomputes coverage', () => {
    const card = makeCard()
    const result = applyExtraPantryToCard(card, new Set(['onion']))

    expect(result.matched_ingredients).toEqual(['Chicken Breast', 'Onion'])
    expect(result.missing_ingredients.map((r) => r.canonical_id)).toEqual(['garlic'])
    expect(result.pantry_coverage).toBeCloseTo(2 / 4)
  })

  it('recomputes estimated cost as the sum of remaining missing items', () => {
    const card = makeCard()
    const result = applyExtraPantryToCard(card, new Set(['onion']))
    expect(result.estimated_additional_spend_aed).toBe(1.5)
  })

  it('marks cost unavailable (never a fabricated number) if a remaining item is incomplete', () => {
    const card = makeCard({
      missing_ingredients: [
        { raw_name: 'onion', canonical_id: 'onion', display_name: 'Onion', estimated_cost_aed: 2.5, price_complete: true },
        { raw_name: 'saffron', canonical_id: 'saffron', display_name: 'Saffron', estimated_cost_aed: null, price_complete: false },
      ],
    })
    const result = applyExtraPantryToCard(card, new Set(['onion']))
    expect(result.price_complete).toBe(false)
    expect(result.estimated_additional_spend_aed).toBeNull()
    // Never AED 0 for an unknown price.
    expect(result.estimated_additional_spend_aed).not.toBe(0)
  })

  it('deduplicates against an ingredient already in the matched list', () => {
    const card = makeCard({ matched_ingredients: ['Chicken Breast', 'Onion'] })
    const result = applyExtraPantryToCard(card, new Set(['onion']))
    expect(result.matched_ingredients.filter((n) => n === 'Onion')).toHaveLength(1)
  })

  it('never promotes an unresolved (canonical_id null) ingredient into matched', () => {
    const card = makeCard()
    // "unresolved" is not a canonical id present on any missing row,
    // so this must be a no-op regardless of what the caller passes.
    const result = applyExtraPantryToCard(card, new Set(['some_random_unresolved_term']))
    expect(result).toBe(card)
  })

  it('handles multiple ingredients checked at once', () => {
    const card = makeCard()
    const result = applyExtraPantryToCard(card, new Set(['onion', 'garlic']))
    expect(result.missing_ingredients).toEqual([])
    expect(result.pantry_coverage).toBeCloseTo(3 / 4)
    expect(result.estimated_additional_spend_aed).toBe(0)
  })
})

describe('applyExtraPantryToResponse', () => {
  it('updates every card in both recommendations and closest_alternatives', () => {
    const response = {
      recommendations: [makeCard({ recipe_id: 'a' }), makeCard({ recipe_id: 'b' })],
      closest_alternatives: [makeCard({ recipe_id: 'c' })],
    }
    const result = applyExtraPantryToResponse(response, new Set(['onion']))

    for (const card of [...result.recommendations, ...result.closest_alternatives]) {
      expect(card.matched_ingredients).toContain('Onion')
    }
  })

  it('returns the same response reference when the extra pantry set is empty', () => {
    const response = { recommendations: [makeCard()], closest_alternatives: [] }
    expect(applyExtraPantryToResponse(response, new Set())).toBe(response)
  })
})
