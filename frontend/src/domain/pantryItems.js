// Deterministic helpers for the pantry chip list shape used by
// IngredientAutocomplete/App: { id, label, canonical_id, unresolved }.
// Kept separate from domain/pantryRecompute.js, which recomputes
// recipe-card match state -- this module only shapes/validates the raw
// pantry list itself (used when restoring it from local storage,
// ticket section 5.1: "duplicates do not appear").

function isValidItem(item) {
  return Boolean(item) && typeof item === 'object' && typeof item.label === 'string' && item.label.trim().length > 0
}

// A resolved item is deduped by canonical_id (the taxonomy identity);
// an unresolved item has no canonical_id, so it's deduped by its raw
// label instead -- the same rule App.jsx already applies when merging
// "I have this" confirmations back into the pantry.
function dedupeKey(item) {
  return item.canonical_id ? `c:${item.canonical_id}` : `r:${item.label.trim().toLowerCase()}`
}

export function dedupePantryItems(items) {
  if (!Array.isArray(items)) return []
  const seen = new Set()
  const result = []
  for (const item of items) {
    if (!isValidItem(item)) continue
    const key = dedupeKey(item)
    if (seen.has(key)) continue
    seen.add(key)
    result.push(item)
  }
  return result
}
