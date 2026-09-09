import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { HISTORY_LIMIT, useRecentSearches } from './useRecentSearches'

function formState(overrides = {}) {
  return {
    pantryItems: [{ id: 'rice', label: 'Rice', canonical_id: 'rice', unresolved: false }],
    excludedItems: [],
    servings: 4,
    totalTimeMinutes: 30,
    allowHardDifficulty: false,
    cuisine: null,
    cuisineStrict: false,
    budgetAed: null,
    ...overrides,
  }
}

describe('useRecentSearches', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('starts empty when nothing is stored', () => {
    const { result } = renderHook(() => useRecentSearches())
    expect(result.current.history).toEqual([])
  })

  it('records a search parameter snapshot, most recent first', () => {
    const { result } = renderHook(() => useRecentSearches())
    act(() => result.current.recordSearch(formState({ cuisine: 'Italian' })))
    act(() => result.current.recordSearch(formState({ cuisine: 'Asian' })))
    expect(result.current.history).toHaveLength(2)
    expect(result.current.history[0].cuisine).toBe('Asian')
    expect(result.current.history[1].cuisine).toBe('Italian')
  })

  it('never stores an LLM response or provider payload -- only search parameters', () => {
    const { result } = renderHook(() => useRecentSearches())
    act(() => result.current.recordSearch(formState()))
    const entry = result.current.history[0]
    expect(Object.keys(entry).sort()).toEqual(
      ['allowHardDifficulty', 'budgetAed', 'cuisine', 'cuisineStrict', 'excludedItems', 'pantryItems', 'servings', 'timestamp', 'totalTimeMinutes'].sort(),
    )
  })

  it(`caps history at ${HISTORY_LIMIT} entries, dropping the oldest`, () => {
    const { result } = renderHook(() => useRecentSearches())
    for (let i = 0; i < HISTORY_LIMIT + 3; i++) {
      act(() => result.current.recordSearch(formState({ servings: i })))
    }
    expect(result.current.history).toHaveLength(HISTORY_LIMIT)
    // Most recent (servings = HISTORY_LIMIT + 2) survives; the oldest are dropped.
    expect(result.current.history[0].servings).toBe(HISTORY_LIMIT + 2)
  })

  it('persists across a remount', () => {
    const { result, unmount } = renderHook(() => useRecentSearches())
    act(() => result.current.recordSearch(formState()))
    unmount()

    const { result: second } = renderHook(() => useRecentSearches())
    expect(second.current.history).toHaveLength(1)
  })

  it('clearHistory empties both state and storage', () => {
    const { result } = renderHook(() => useRecentSearches())
    act(() => result.current.recordSearch(formState()))
    act(() => result.current.clearHistory())
    expect(result.current.history).toEqual([])

    const { result: second } = renderHook(() => useRecentSearches())
    expect(second.current.history).toEqual([])
  })
})
