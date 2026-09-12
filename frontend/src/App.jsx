import { useCallback, useEffect, useMemo, useState } from 'react'
import { Header } from './components/Header'
import { SearchForm } from './components/SearchForm'
import { LoadingState } from './components/LoadingState'
import { RecipeGrid } from './components/RecipeGrid'
import { ClosestMatchNotice } from './components/ClosestMatchNotice'
import { RecipeDetail } from './components/RecipeDetail'
import { EmptyState } from './components/EmptyState'
import { ErrorState } from './components/ErrorState'
import { LocalDataPanel } from './components/LocalDataPanel'
import { postRecommend } from './services/api'
import { applyExtraPantryToResponse } from './domain/pantryRecompute'
import { dedupePantryItems } from './domain/pantryItems'
import { readVersioned, writeVersioned, clearVersioned } from './utils/storage'
import { useRecentSearches } from './hooks/useRecentSearches'
import { useSavedRecipes } from './hooks/useSavedRecipes'
import { HeroDecor } from './components/decor/CulinaryMotifs'
import './App.css'

const PANTRY_STORAGE_KEY = 'pantry'
const PANTRY_STORAGE_VERSION = 1
const PREFS_STORAGE_KEY = 'form-prefs'
const PREFS_STORAGE_VERSION = 1

const DEFAULT_FORM_STATE = {
  pantryItems: [],
  excludedItems: [],
  totalTimeMinutes: 30,
  servings: 4,
  allowHardDifficulty: false,
  cuisine: null,
  cuisineStrict: false,
  budgetAed: null,
}

// Ticket section 5.2 + explicit Founder decision: budget is never
// restored from local storage, so it always starts empty/unset on
// reload regardless of what was searched last session -- only
// servings/time/difficulty/cuisine persist.
function loadInitialFormState() {
  const persistedPantry = dedupePantryItems(readVersioned(PANTRY_STORAGE_KEY, PANTRY_STORAGE_VERSION, []))
  const prefs = readVersioned(PREFS_STORAGE_KEY, PREFS_STORAGE_VERSION, {})
  return {
    ...DEFAULT_FORM_STATE,
    pantryItems: persistedPantry,
    servings: typeof prefs.servings === 'number' ? prefs.servings : DEFAULT_FORM_STATE.servings,
    totalTimeMinutes: typeof prefs.totalTimeMinutes === 'number' ? prefs.totalTimeMinutes : DEFAULT_FORM_STATE.totalTimeMinutes,
    allowHardDifficulty: typeof prefs.allowHardDifficulty === 'boolean' ? prefs.allowHardDifficulty : DEFAULT_FORM_STATE.allowHardDifficulty,
    cuisine: typeof prefs.cuisine === 'string' ? prefs.cuisine : DEFAULT_FORM_STATE.cuisine,
  }
}

function buildPayload(formState) {
  return {
    ingredients: formState.pantryItems.map((item) => item.label),
    excluded_ingredients: formState.excludedItems.map((item) => item.label),
    budget_aed: formState.budgetAed,
    cuisine: formState.cuisine,
    cuisine_strict: formState.cuisineStrict,
    servings: formState.servings,
    max_total_time_minutes: formState.totalTimeMinutes,
    allow_hard_difficulty: formState.allowHardDifficulty,
  }
}

export default function App() {
  const [formState, setFormState] = useState(loadInitialFormState)
  const [view, setView] = useState('search') // 'search' | 'loading' | 'results' | 'error'
  const [response, setResponse] = useState(null)
  const [error, setError] = useState(null)
  const [selectedCardId, setSelectedCardId] = useState(null)
  const [localDataOpen, setLocalDataOpen] = useState(false)
  const { history, recordSearch, clearHistory } = useRecentSearches()
  const { saved, isSaved, toggleSaved, removeSaved, clearSaved } = useSavedRecipes()

  useEffect(() => {
    writeVersioned(PANTRY_STORAGE_KEY, PANTRY_STORAGE_VERSION, formState.pantryItems)
  }, [formState.pantryItems])

  useEffect(() => {
    writeVersioned(PREFS_STORAGE_KEY, PREFS_STORAGE_VERSION, {
      servings: formState.servings,
      totalTimeMinutes: formState.totalTimeMinutes,
      allowHardDifficulty: formState.allowHardDifficulty,
      cuisine: formState.cuisine,
    })
  }, [formState.servings, formState.totalTimeMinutes, formState.allowHardDifficulty, formState.cuisine])
  // "I have this" (ticket section 2): canonical_id -> display_name, for
  // ingredients the user confirms they have after seeing results.
  // Frontend-only, deterministic state -- never sent anywhere until the
  // user explicitly asks to "Refresh recommendations".
  const [extraPantry, setExtraPantry] = useState(() => new Map())
  // Priority 3 (ticket, PR #15 correction pass, 2026-09-08): the same
  // idea for UNRESOLVED ingredient rows, keyed by the backend's
  // deterministic raw-text identity_key (never a canonical_id) ->
  // raw_name. Confirming one never promotes it into the taxonomy or
  // pricing tables -- it only records the user's own confirmed raw
  // pantry state for this session.
  const [extraUnresolvedPantry, setExtraUnresolvedPantry] = useState(() => new Map())
  // Priority 4 (ticket, PR #15 correction pass, 2026-09-08): how many
  // additional_options are currently revealed, in batches of 3. Purely
  // a display cursor over data the search already returned -- "Show
  // more options" never calls the backend.
  const [visibleAdditionalCount, setVisibleAdditionalCount] = useState(0)

  const runSearch = useCallback(async (currentFormState) => {
    setView('loading')
    setError(null)
    // Recorded regardless of outcome -- history is for reconstructing
    // what was searched, not for whether it succeeded (ticket 5.3).
    recordSearch(currentFormState)
    try {
      const result = await postRecommend(buildPayload(currentFormState))
      setResponse(result)
      setExtraPantry(new Map())
      setExtraUnresolvedPantry(new Map())
      setVisibleAdditionalCount(0)
      setView('results')
    } catch (err) {
      setError(err)
      setView('error')
    }
  }, [recordSearch])

  const extraCanonicalIds = useMemo(() => new Set(extraPantry.keys()), [extraPantry])
  const extraUnresolvedIdentityKeys = useMemo(() => new Set(extraUnresolvedPantry.keys()), [extraUnresolvedPantry])
  // Priority 4: the SAME constraints the current search used, so a
  // local rerank scores cost/cuisine identically to how the backend
  // originally ranked these cards (backend/app/domain/ranker.py's
  // exact contract: budget_aed / cuisine_preference).
  const rankingConstraints = useMemo(
    () => ({ budgetAed: formState.budgetAed, cuisinePreference: formState.cuisine }),
    [formState.budgetAed, formState.cuisine],
  )

  // Deterministic, frontend-only recompute -- never calls the backend
  // or the LLM merely because a checkbox was clicked.
  const displayResponse = useMemo(
    () => applyExtraPantryToResponse(response, extraCanonicalIds, extraUnresolvedIdentityKeys, rankingConstraints),
    [response, extraCanonicalIds, extraUnresolvedIdentityKeys, rankingConstraints],
  )

  const selectedCard = displayResponse
    ? [
        ...displayResponse.recommendations,
        ...(displayResponse.additional_options ?? []),
        ...displayResponse.closest_alternatives,
      ].find((card) => card.recipe_id === selectedCardId) ?? null
    : null

  function handleSubmit() {
    runSearch(formState)
  }

  function handleNewSearch() {
    setView('search')
    setResponse(null)
    setError(null)
    setExtraPantry(new Map())
    setExtraUnresolvedPantry(new Map())
    setVisibleAdditionalCount(0)
  }

  // Priority 4: reveals 3 more already-evaluated candidates. Purely a
  // local counter over displayResponse.additional_options -- makes no
  // Claude or RecipeAPI.io call.
  function handleShowMoreOptions() {
    setVisibleAdditionalCount((prev) => prev + 3)
  }

  function handleMarkHave(canonicalId) {
    if (!selectedCard) return
    const row = selectedCard.missing_ingredients.find((r) => r.canonical_id === canonicalId)
    if (!row) return
    setExtraPantry((prev) => {
      const next = new Map(prev)
      next.set(canonicalId, row.display_name)
      return next
    })
  }

  // Priority 3 (ticket, PR #15 correction pass, 2026-09-08): identical
  // shape to handleMarkHave above, but for an UNRESOLVED row -- keyed by
  // identity_key (never a canonical_id), so it can never be promoted
  // into the taxonomy.
  function handleMarkHaveUnresolved(identityKey, rawName) {
    if (!identityKey) return
    setExtraUnresolvedPantry((prev) => {
      const next = new Map(prev)
      next.set(identityKey, rawName)
      return next
    })
  }

  function handleRefreshRecommendations() {
    if (extraPantry.size === 0 && extraUnresolvedPantry.size === 0) return
    const existingCanonicalIds = new Set(formState.pantryItems.map((item) => item.canonical_id).filter(Boolean))
    const newChips = [...extraPantry.entries()]
      .filter(([canonicalId]) => !existingCanonicalIds.has(canonicalId))
      .map(([canonicalId, displayName]) => ({
        id: canonicalId,
        label: displayName,
        canonical_id: canonicalId,
        unresolved: false,
      }))
    // Priority 3: confirmed-unresolved raw text is submitted as raw
    // pantry input too ("include confirmed unresolved ingredients as
    // raw pantry inputs"), with no canonical_id -- if the backend still
    // cannot normalize it, it is preserved as unresolved again, never
    // silently promoted. Deduped by raw label so a term the user already
    // typed into the pantry isn't sent twice.
    const existingRawLabels = new Set(formState.pantryItems.map((item) => item.label.trim().toLowerCase()))
    const newUnresolvedChips = [...extraUnresolvedPantry.entries()]
      .filter(([, rawName]) => !existingRawLabels.has(rawName.trim().toLowerCase()))
      .map(([identityKey, rawName]) => ({
        id: `unresolved:${identityKey}`,
        label: rawName,
        canonical_id: null,
        unresolved: true,
      }))
    const updatedFormState = {
      ...formState,
      pantryItems: [...formState.pantryItems, ...newChips, ...newUnresolvedChips],
    }
    setFormState(updatedFormState)
    runSearch(updatedFormState)
  }

  function handleClearPantry() {
    setFormState((prev) => ({ ...prev, pantryItems: [] }))
  }

  // Clears every local-storage key Module F introduced and resets the
  // live form back to defaults in one action (ticket section 5.5) --
  // "no accounts" means this browser's storage is the only place any
  // of this state lives, so there's nothing else to reset server-side.
  function handleClearAllLocalData() {
    setFormState(DEFAULT_FORM_STATE)
    clearVersioned(PANTRY_STORAGE_KEY)
    clearVersioned(PREFS_STORAGE_KEY)
    clearHistory()
    clearSaved()
  }

  // Re-running a specific past search deliberately reproduces it
  // exactly, budget included -- unlike the live form's default (which
  // never restores a stale budget on reload), this is an explicit,
  // user-initiated action naming exactly which search to repeat.
  function handleRerunSearch(entry) {
    const nextFormState = {
      ...formState,
      pantryItems: entry.pantryItems,
      excludedItems: entry.excludedItems,
      servings: entry.servings,
      totalTimeMinutes: entry.totalTimeMinutes,
      allowHardDifficulty: entry.allowHardDifficulty,
      cuisine: entry.cuisine,
      cuisineStrict: entry.cuisineStrict,
      budgetAed: entry.budgetAed,
    }
    setFormState(nextFormState)
    setSelectedCardId(null)
    setLocalDataOpen(false)
    runSearch(nextFormState)
  }

  function handleShowLongerRecipes() {
    // Must explicitly change the user's time constraint (never a
    // silent relaxation) and rerun the normal search (ticket section 3).
    const nextTime = Math.min(600, formState.totalTimeMinutes + 30)
    const updatedFormState = { ...formState, totalTimeMinutes: nextTime }
    setFormState(updatedFormState)
    runSearch(updatedFormState)
  }

  return (
    <div className="app-shell">
      {/* Rendered at the app-shell level (a true full-viewport layer),
          not nested inside the 1080px-wide centered .container --
          anchoring it there was exactly what made the imagery read as
          a boxed rectangle instead of a page-level background
          (visual-correction pass). Still gated to the search view
          only. */}
      {view === 'search' ? <HeroDecor /> : null}
      <Header onBrandClick={handleNewSearch} onOpenLocalData={() => setLocalDataOpen(true)} />
      <main className="container app-main">
        {view === 'search' ? (
          <div className="hero-section">
            <div className="hero">
              <span className="eyebrow hero__eyebrow">Pantry-First Recipes</span>
              <h1 className="hero__title">Cook smarter with what you already have.</h1>
              <p className="hero__subtitle">
                PantryPilot searches real recipes based on ingredients you already have -- it never invents recipes.
              </p>
            </div>
            <SearchForm formState={formState} onChange={setFormState} onSubmit={handleSubmit} submitting={false} />
          </div>
        ) : null}

        {view === 'loading' ? <LoadingState /> : null}

        {view === 'error' ? (
          <ErrorState message={error?.message} retryable={error?.retryable} onRetry={() => runSearch(formState)} />
        ) : null}

        {view === 'results' && displayResponse ? (
          <ResultsView
            response={displayResponse}
            onOpen={(card) => setSelectedCardId(card.recipe_id)}
            onNewSearch={handleNewSearch}
            pendingHaveCount={extraPantry.size + extraUnresolvedPantry.size}
            onRefreshRecommendations={handleRefreshRecommendations}
            onShowLongerRecipes={handleShowLongerRecipes}
            currentTotalTimeMinutes={formState.totalTimeMinutes}
            visibleAdditionalCount={visibleAdditionalCount}
            onShowMoreOptions={handleShowMoreOptions}
            isSaved={isSaved}
          />
        ) : null}
      </main>

      {selectedCard ? (
        <RecipeDetail
          card={selectedCard}
          onClose={() => setSelectedCardId(null)}
          onMarkHave={handleMarkHave}
          onMarkHaveUnresolved={handleMarkHaveUnresolved}
          saved={isSaved(selectedCard.recipe_id)}
          onToggleSaved={toggleSaved}
        />
      ) : null}

      {localDataOpen ? (
        <LocalDataPanel
          onClose={() => setLocalDataOpen(false)}
          history={history}
          onRerunSearch={handleRerunSearch}
          onClearHistory={clearHistory}
          saved={saved}
          onRemoveSaved={removeSaved}
          onClearSaved={clearSaved}
          onClearPantry={handleClearPantry}
          onClearAll={handleClearAllLocalData}
        />
      ) : null}
    </div>
  )
}

function ResultsView({
  response,
  onOpen,
  onNewSearch,
  pendingHaveCount,
  onRefreshRecommendations,
  onShowLongerRecipes,
  currentTotalTimeMinutes,
  visibleAdditionalCount,
  onShowMoreOptions,
  isSaved,
}) {
  const hasExact = response.recommendations.length > 0
  const additionalOptions = response.additional_options ?? []
  const closestAlternatives = response.closest_alternatives ?? []
  // Priority 4: additional_options are only ever meaningful alongside
  // actual top-3 final recommendations -- the closest-alternatives
  // (fallback) path never has a "show more" reserve pool, since those
  // candidates are never same-anchor matches.
  const revealedAdditional = hasExact ? additionalOptions.slice(0, visibleAdditionalCount) : []
  const cardsToShow = hasExact ? [...response.recommendations, ...revealedAdditional] : closestAlternatives
  const hasMoreToShow = hasExact && visibleAdditionalCount < additionalOptions.length
  // PR #15 fifth correction pass (2026-09-08, product decision):
  // non-anchor fallback candidates never pad recommendations anymore --
  // they live in closest_alternatives, shown as an explicitly separate
  // section BELOW genuine recommendations (never mixed into the same
  // grid), and only when there actually are exact/same-anchor matches
  // to be "closest alternatives" TO. When there are no exact matches at
  // all, closest_alternatives already IS the primary content above.
  const hasSeparateClosestAlternatives = hasExact && closestAlternatives.length > 0

  if (!hasExact && cardsToShow.length === 0) {
    return <EmptyState onNewSearch={onNewSearch} />
  }

  return (
    <div className="results-view">
      <div className="results-header">
        <div>
          <button type="button" onClick={onNewSearch} className="results-header__back">
            ← New search
          </button>
          <h2 className="results-header__title">{hasExact ? 'Best matches for you' : 'Closest options for you'}</h2>
        </div>
        {pendingHaveCount > 0 ? (
          <button type="button" className="btn btn-secondary" onClick={onRefreshRecommendations}>
            Refresh recommendations
          </button>
        ) : null}
      </div>

      {response.pantry_unresolved.length > 0 ? (
        <p className="notice-text--warning">
          Not recognized and not used in this search: {response.pantry_unresolved.join(', ')}
        </p>
      ) : null}

      {response.higher_match_time_excluded ? (
        <div className="card notice-card">
          <p>Some better pantry matches were excluded because they exceeded your {currentTotalTimeMinutes}-minute limit.</p>
          <button type="button" className="btn btn-secondary" onClick={onShowLongerRecipes}>
            Show longer recipes
          </button>
        </div>
      ) : null}

      {!hasExact ? <ClosestMatchNotice hasExactMatches={false} /> : null}

      <RecipeGrid cards={cardsToShow} onOpen={onOpen} isSaved={isSaved} />

      {hasMoreToShow ? (
        <div className="show-more-row">
          <button type="button" className="btn btn-secondary" onClick={onShowMoreOptions}>
            Show more options
          </button>
        </div>
      ) : null}

      {hasSeparateClosestAlternatives ? (
        <div className="card other-options-panel">
          <div className="other-options-panel__intro">
            <h3>Other options</h3>
            <p>These use a different main ingredient than what you searched for.</p>
          </div>
          <RecipeGrid cards={closestAlternatives} onOpen={onOpen} isSaved={isSaved} />
        </div>
      ) : null}
    </div>
  )
}
