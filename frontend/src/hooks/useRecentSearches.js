import { useCallback, useState } from 'react'
import { readVersioned, writeVersioned } from '../utils/storage'

const KEY = 'history'
const VERSION = 1
// Ticket section 5.3 asks for "a small bounded number such as 5-10" --
// 8 keeps the panel scannable in one screen without scrolling on a
// typical phone while still covering a normal day's worth of searches.
export const HISTORY_LIMIT = 8

// Stores only what's needed to reconstruct and rerun a search -- never
// the LLM response or provider recipe payloads it produced (ticket
// section 5.3).
function toHistoryEntry(formState) {
  return {
    pantryItems: formState.pantryItems,
    excludedItems: formState.excludedItems,
    servings: formState.servings,
    totalTimeMinutes: formState.totalTimeMinutes,
    allowHardDifficulty: formState.allowHardDifficulty,
    cuisine: formState.cuisine,
    cuisineStrict: formState.cuisineStrict,
    budgetAed: formState.budgetAed,
    timestamp: Date.now(),
  }
}

export function useRecentSearches() {
  const [history, setHistory] = useState(() => readVersioned(KEY, VERSION, []))

  const recordSearch = useCallback((formState) => {
    setHistory((prev) => {
      const next = [toHistoryEntry(formState), ...prev].slice(0, HISTORY_LIMIT)
      writeVersioned(KEY, VERSION, next)
      return next
    })
  }, [])

  const clearHistory = useCallback(() => {
    setHistory([])
    writeVersioned(KEY, VERSION, [])
  }, [])

  return { history, recordSearch, clearHistory }
}
