import { useCallback, useMemo, useState } from 'react'
import { Header } from './components/Header'
import { SearchForm } from './components/SearchForm'
import { LoadingState } from './components/LoadingState'
import { RecipeGrid } from './components/RecipeGrid'
import { ClosestMatchNotice } from './components/ClosestMatchNotice'
import { RecipeDetail } from './components/RecipeDetail'
import { EmptyState } from './components/EmptyState'
import { ErrorState } from './components/ErrorState'
import { postRecommend } from './services/api'
import { applyExtraPantryToResponse } from './domain/pantryRecompute'

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
  const [formState, setFormState] = useState(DEFAULT_FORM_STATE)
  const [view, setView] = useState('search') // 'search' | 'loading' | 'results' | 'error'
  const [response, setResponse] = useState(null)
  const [error, setError] = useState(null)
  const [selectedCardId, setSelectedCardId] = useState(null)
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

  const runSearch = useCallback(async (currentFormState) => {
    setView('loading')
    setError(null)
    try {
      const result = await postRecommend(buildPayload(currentFormState))
      setResponse(result)
      setExtraPantry(new Map())
      setExtraUnresolvedPantry(new Map())
      setView('results')
    } catch (err) {
      setError(err)
      setView('error')
    }
  }, [])

  const extraCanonicalIds = useMemo(() => new Set(extraPantry.keys()), [extraPantry])
  const extraUnresolvedIdentityKeys = useMemo(() => new Set(extraUnresolvedPantry.keys()), [extraUnresolvedPantry])

  // Deterministic, frontend-only recompute -- never calls the backend
  // or the LLM merely because a checkbox was clicked.
  const displayResponse = useMemo(
    () => applyExtraPantryToResponse(response, extraCanonicalIds, extraUnresolvedIdentityKeys),
    [response, extraCanonicalIds, extraUnresolvedIdentityKeys],
  )

  const selectedCard = displayResponse
    ? [...displayResponse.recommendations, ...displayResponse.closest_alternatives].find(
        (card) => card.recipe_id === selectedCardId,
      ) ?? null
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

  function handleShowLongerRecipes() {
    // Must explicitly change the user's time constraint (never a
    // silent relaxation) and rerun the normal search (ticket section 3).
    const nextTime = Math.min(600, formState.totalTimeMinutes + 30)
    const updatedFormState = { ...formState, totalTimeMinutes: nextTime }
    setFormState(updatedFormState)
    runSearch(updatedFormState)
  }

  return (
    <>
      <Header onBrandClick={handleNewSearch} />
      <main className="container" style={{ paddingTop: 'var(--space-6)', paddingBottom: 'var(--space-7)' }}>
        {view === 'search' ? (
          <>
            <div style={{ textAlign: 'center', maxWidth: 560, margin: '0 auto var(--space-6)' }}>
              <h1 style={{ fontSize: 30, margin: '0 0 var(--space-2)' }}>
                Cook smarter with what you already have.
              </h1>
              <p style={{ color: 'var(--color-text-muted)', margin: 0 }}>
                PantryPilot searches real recipes based on ingredients you already have -- it never invents recipes.
              </p>
            </div>
            <SearchForm formState={formState} onChange={setFormState} onSubmit={handleSubmit} submitting={false} />
          </>
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
          />
        ) : null}
      </main>

      {selectedCard ? (
        <RecipeDetail
          card={selectedCard}
          onClose={() => setSelectedCardId(null)}
          onMarkHave={handleMarkHave}
          onMarkHaveUnresolved={handleMarkHaveUnresolved}
        />
      ) : null}
    </>
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
}) {
  const hasExact = response.recommendations.length > 0
  const cardsToShow = hasExact ? response.recommendations : response.closest_alternatives

  if (!hasExact && cardsToShow.length === 0) {
    return <EmptyState onNewSearch={onNewSearch} />
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
        <div>
          <button type="button" onClick={onNewSearch} className="search-form__more-toggle" style={{ padding: 0, marginBottom: 4 }}>
            ← New search
          </button>
          <h2 style={{ margin: 0 }}>{hasExact ? 'Best matches for you' : 'Closest options for you'}</h2>
        </div>
        {pendingHaveCount > 0 ? (
          <button type="button" className="btn btn-secondary" onClick={onRefreshRecommendations}>
            Refresh recommendations
          </button>
        ) : null}
      </div>

      {response.pantry_unresolved.length > 0 ? (
        <p style={{ fontSize: 13, color: 'var(--color-warning)', margin: 0 }}>
          Not recognized and not used in this search: {response.pantry_unresolved.join(', ')}
        </p>
      ) : null}

      {response.higher_match_time_excluded ? (
        <div className="card" style={{ padding: 'var(--space-4)', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 'var(--space-3)' }}>
          <p style={{ margin: 0, fontSize: 13, color: 'var(--color-text)' }}>
            Some better pantry matches were excluded because they exceeded your {currentTotalTimeMinutes}-minute limit.
          </p>
          <button type="button" className="btn btn-secondary" onClick={onShowLongerRecipes}>
            Show longer recipes
          </button>
        </div>
      ) : null}

      {!hasExact ? <ClosestMatchNotice hasExactMatches={false} /> : null}

      <RecipeGrid cards={cardsToShow} onOpen={onOpen} />
    </div>
  )
}
