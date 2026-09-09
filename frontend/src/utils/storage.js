// Versioned localStorage helper (Module F, ticket section 5.1: "Use
// versioned storage so future schema changes can safely
// invalidate/migrate old data"). Every read/write is wrapped so private
// browsing, disabled storage, a full quota, or corrupted JSON degrades
// to in-memory-only behavior -- it must never throw or crash the app
// (ticket section 5, "no accounts" persistence must be purely additive).
const NAMESPACE = 'pantrypilot'

function storageKey(key) {
  return `${NAMESPACE}:${key}`
}

// Returns `fallback` whenever the stored value is missing, malformed,
// or was written by a different schema version -- there is no
// migration logic yet because there is only one version of each key so
// far; a future bump just needs to add a translation step here instead
// of changing this contract.
export function readVersioned(key, version, fallback) {
  try {
    const raw = window.localStorage.getItem(storageKey(key))
    if (!raw) return fallback
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object' || parsed.version !== version) return fallback
    return parsed.data
  } catch {
    return fallback
  }
}

export function writeVersioned(key, version, data) {
  try {
    window.localStorage.setItem(storageKey(key), JSON.stringify({ version, data }))
  } catch {
    // Storage disabled/full/private browsing -- the app keeps working
    // in-memory for this session, it just won't survive a reload.
  }
}

export function clearVersioned(key) {
  try {
    window.localStorage.removeItem(storageKey(key))
  } catch {
    // ignore -- nothing to clean up if storage isn't available anyway
  }
}
