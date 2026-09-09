import { describe, expect, it } from 'vitest'
import { dedupePantryItems } from './pantryItems'

describe('dedupePantryItems', () => {
  it('deduplicates resolved items by canonical_id', () => {
    const items = [
      { id: 'rice', label: 'Rice', canonical_id: 'rice', unresolved: false },
      { id: 'rice', label: 'Rice', canonical_id: 'rice', unresolved: false },
    ]
    expect(dedupePantryItems(items)).toHaveLength(1)
  })

  it('deduplicates unresolved items by case-insensitive trimmed label, not id', () => {
    const items = [
      { id: 'unresolved:mystery sauce', label: 'Mystery Sauce', canonical_id: null, unresolved: true },
      { id: 'unresolved:MYSTERY SAUCE ', label: ' mystery sauce ', canonical_id: null, unresolved: true },
    ]
    expect(dedupePantryItems(items)).toHaveLength(1)
  })

  it('keeps a resolved and an unresolved item with the same label as distinct entries', () => {
    const items = [
      { id: 'onion', label: 'Onion', canonical_id: 'onion', unresolved: false },
      { id: 'unresolved:onion', label: 'Onion', canonical_id: null, unresolved: true },
    ]
    expect(dedupePantryItems(items)).toHaveLength(2)
  })

  it('drops malformed entries instead of throwing', () => {
    expect(dedupePantryItems(null)).toEqual([])
    expect(dedupePantryItems('not-an-array')).toEqual([])
    expect(dedupePantryItems([null, {}, { label: '' }, { label: '   ' }, 42])).toEqual([])
  })

  it('preserves order, keeping the first occurrence of a duplicate', () => {
    const first = { id: 'rice', label: 'Rice', canonical_id: 'rice', unresolved: false }
    const items = [first, { id: 'onion', label: 'Onion', canonical_id: 'onion', unresolved: false }, { ...first }]
    const result = dedupePantryItems(items)
    expect(result.map((i) => i.canonical_id)).toEqual(['rice', 'onion'])
  })
})
