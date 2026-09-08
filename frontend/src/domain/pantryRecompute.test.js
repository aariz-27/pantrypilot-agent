import { describe, expect, it } from 'vitest'
import { applyExtraPantryToCard, applyExtraPantryToResponse } from './pantryRecompute'

function unresolvedRow(rawName, identityKey = rawName.trim().toLowerCase()) {
  return { raw_name: rawName, display_name: rawName, identity_key: identityKey }
}

function makeCard(overrides = {}) {
  return {
    recipe_id: 'recipeapi_io:1',
    matched_ingredients: ['Chicken Breast'],
    missing_ingredients: [
      { raw_name: 'onion', canonical_id: 'onion', display_name: 'Onion', estimated_cost_aed: 2.5, price_complete: true },
      { raw_name: 'garlic', canonical_id: 'garlic', display_name: 'Garlic', estimated_cost_aed: 1.5, price_complete: true },
    ],
    unresolved_ingredients: [unresolvedRow('Some weird sauce')],
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
    // No unresolved ingredients here -- isolates the sum-of-remaining-
    // costs arithmetic from the unresolved-uncertainty rule (covered
    // separately below).
    const card = makeCard({ unresolved_ingredients: [] })
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

  it('handles multiple ingredients checked at once, coverage improves, but cost stays incomplete while an unresolved ingredient remains', () => {
    // Post-review fix (2026-09-08): the default makeCard() fixture
    // carries one unresolved ingredient ("Some weird sauce"), whose
    // price is fundamentally unknown. Checking off every RECOGNIZED
    // missing ingredient must never be read as "nothing left to buy" --
    // that would imply the user needs to spend AED 0 while an unknown-
    // cost required ingredient still exists. price_complete must stay
    // false and the spend must stay null, never a fabricated 0.
    const card = makeCard()
    const result = applyExtraPantryToCard(card, new Set(['onion', 'garlic']))
    expect(result.missing_ingredients).toEqual([])
    expect(result.pantry_coverage).toBeCloseTo(3 / 4)
    expect(result.price_complete).toBe(false)
    expect(result.estimated_additional_spend_aed).toBeNull()
    expect(result.estimated_additional_spend_aed).not.toBe(0)
  })

  it('AED 0 is valid only when all required ingredients are matched AND there are no unresolved ingredients', () => {
    const fullyResolvableCard = makeCard({ unresolved_ingredients: [] })
    const result = applyExtraPantryToCard(fullyResolvableCard, new Set(['onion', 'garlic']))

    expect(result.missing_ingredients).toEqual([])
    expect(result.unresolved_ingredients).toEqual([])
    expect(result.price_complete).toBe(true)
    expect(result.estimated_additional_spend_aed).toBe(0)
  })

  it('cost stays incomplete when ingredients are fully matched but an unresolved ingredient alone remains', () => {
    const card = makeCard({
      missing_ingredients: [{ raw_name: 'onion', canonical_id: 'onion', display_name: 'Onion', estimated_cost_aed: 2.5, price_complete: true }],
      unresolved_ingredients: [unresolvedRow('Mystery spice blend')],
    })
    const result = applyExtraPantryToCard(card, new Set(['onion']))

    expect(result.missing_ingredients).toEqual([])
    expect(result.unresolved_ingredients).toEqual([unresolvedRow('Mystery spice blend')])
    expect(result.price_complete).toBe(false)
    expect(result.estimated_additional_spend_aed).toBeNull()
  })
})

describe('applyExtraPantryToCard -- unresolved ingredient "I have this" (Priority 3, PR #15 correction pass)', () => {
  it('moves a confirmed-unresolved row into matched_ingredients and out of unresolved_ingredients', () => {
    const card = makeCard()
    const result = applyExtraPantryToCard(card, new Set(), new Set(['some weird sauce']))

    expect(result.matched_ingredients).toEqual(['Chicken Breast', 'Some weird sauce'])
    expect(result.unresolved_ingredients).toEqual([])
  })

  it('increases pantry_coverage when an unresolved row is confirmed', () => {
    const card = makeCard()
    const result = applyExtraPantryToCard(card, new Set(), new Set(['some weird sauce']))
    // total = 1 matched + 2 missing + 1 unresolved = 4; new matched = 2
    expect(result.pantry_coverage).toBeCloseTo(2 / 4)
  })

  it('never assigns a canonical_id -- the confirmed row carries no trusted taxonomy identity', () => {
    const card = makeCard()
    const result = applyExtraPantryToCard(card, new Set(), new Set(['some weird sauce']))
    // matched_ingredients is (and remains) a plain display-name array,
    // never a canonical-id-bearing object -- confirming an unresolved
    // row does not change that shape or fabricate an id anywhere.
    expect(result.matched_ingredients.every((name) => typeof name === 'string')).toBe(true)
  })

  it('never fabricates a price for a confirmed-unresolved ingredient', () => {
    const card = makeCard({
      missing_ingredients: [],
      unresolved_ingredients: [unresolvedRow('Some weird sauce')],
      matched_ingredients: ['Chicken Breast'],
    })
    const result = applyExtraPantryToCard(card, new Set(), new Set(['some weird sauce']))
    // Nothing left missing or unresolved -- cost is genuinely complete
    // at 0, but never because the unresolved ingredient itself was
    // priced.
    expect(result.price_complete).toBe(true)
    expect(result.estimated_additional_spend_aed).toBe(0)
  })

  it('cost stays incomplete while a DIFFERENT unresolved ingredient remains unconfirmed', () => {
    const card = makeCard({
      missing_ingredients: [],
      unresolved_ingredients: [unresolvedRow('Some weird sauce'), unresolvedRow('Another mystery item')],
      matched_ingredients: ['Chicken Breast'],
    })
    const result = applyExtraPantryToCard(card, new Set(), new Set(['some weird sauce']))
    expect(result.unresolved_ingredients).toEqual([unresolvedRow('Another mystery item')])
    expect(result.price_complete).toBe(false)
    expect(result.estimated_additional_spend_aed).toBeNull()
  })

  it('is a no-op when the identity key does not match any unresolved row', () => {
    const card = makeCard()
    const result = applyExtraPantryToCard(card, new Set(), new Set(['completely different text']))
    expect(result).toBe(card)
  })

  it('applies both a recognized missing confirmation and an unresolved confirmation together', () => {
    const card = makeCard()
    const result = applyExtraPantryToCard(card, new Set(['onion']), new Set(['some weird sauce']))
    expect(result.matched_ingredients).toEqual(['Chicken Breast', 'Onion', 'Some weird sauce'])
    expect(result.missing_ingredients.map((r) => r.canonical_id)).toEqual(['garlic'])
    expect(result.unresolved_ingredients).toEqual([])
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

  it('returns the same response reference when both extra pantry sets are empty', () => {
    const response = { recommendations: [makeCard()], closest_alternatives: [] }
    expect(applyExtraPantryToResponse(response, new Set(), new Set())).toBe(response)
  })

  it('updates the same unresolved ingredient across multiple cards by identity_key (ticket: safe identity matching)', () => {
    const response = {
      recommendations: [
        makeCard({ recipe_id: 'a', unresolved_ingredients: [unresolvedRow('Some Weird Sauce', 'some weird sauce')] }),
        makeCard({ recipe_id: 'b', unresolved_ingredients: [unresolvedRow('some weird sauce!!', 'some weird sauce')] }),
      ],
      closest_alternatives: [],
    }
    const result = applyExtraPantryToResponse(response, new Set(), new Set(['some weird sauce']))

    for (const card of result.recommendations) {
      expect(card.unresolved_ingredients).toEqual([])
      expect(card.matched_ingredients).toContain('Chicken Breast')
    }
    expect(result.recommendations[0].matched_ingredients).toContain('Some Weird Sauce')
    expect(result.recommendations[1].matched_ingredients).toContain('some weird sauce!!')
  })
})
