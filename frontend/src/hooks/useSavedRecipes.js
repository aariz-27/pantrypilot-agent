import { useCallback, useMemo, useState } from 'react'
import { readVersioned, writeVersioned } from '../utils/storage'

const KEY = 'saved-recipes'
const VERSION = 1

// Minimal, provider-grounded fields only (ticket section 5.4) -- never
// generated recipe content, because PantryPilot has none: recipes are
// always provider-grounded (docs/AGENTS.md recipe-grounding rules).
function toSavedRecord(card) {
  return {
    recipeId: card.recipe_id,
    provider: card.provider,
    title: card.name,
    imageUrl: card.image_url ?? null,
    sourceUrl: card.source_url ?? null,
    timestamp: Date.now(),
  }
}

export function useSavedRecipes() {
  const [saved, setSaved] = useState(() => readVersioned(KEY, VERSION, []))

  const savedIds = useMemo(() => new Set(saved.map((r) => r.recipeId)), [saved])

  const isSaved = useCallback((recipeId) => savedIds.has(recipeId), [savedIds])

  const toggleSaved = useCallback((card) => {
    setSaved((prev) => {
      const exists = prev.some((r) => r.recipeId === card.recipe_id)
      const next = exists
        ? prev.filter((r) => r.recipeId !== card.recipe_id)
        : [toSavedRecord(card), ...prev]
      writeVersioned(KEY, VERSION, next)
      return next
    })
  }, [])

  const removeSaved = useCallback((recipeId) => {
    setSaved((prev) => {
      const next = prev.filter((r) => r.recipeId !== recipeId)
      writeVersioned(KEY, VERSION, next)
      return next
    })
  }, [])

  const clearSaved = useCallback(() => {
    setSaved([])
    writeVersioned(KEY, VERSION, [])
  }, [])

  return { saved, isSaved, toggleSaved, removeSaved, clearSaved }
}
