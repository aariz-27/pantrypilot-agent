import { useCallback, useState } from 'react'
import { Header } from './components/Header'
import { SearchForm } from './components/SearchForm'
import { LoadingState } from './components/LoadingState'
import { RecipeGrid } from './components/RecipeGrid'
import { ClosestMatchNotice } from './components/ClosestMatchNotice'
import { RecipeDetail } from './components/RecipeDetail'
import { EmptyState } from './components/EmptyState'
import { ErrorState } from './components/ErrorState'
import { postRecommend } from './services/api'

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
  const [selectedCard, setSelectedCard] = useState(null)

  const runSearch = useCallback(async (currentFormState) => {
    setView('loading')
    setError(null)
    try {
      const result = await postRecommend(buildPayload(currentFormState))
      setResponse(result)
      setView('results')
    } catch (err) {
      setError(err)
      setView('error')
    }
  }, [])

  function handleSubmit() {
    runSearch(formState)
  }

  function handleNewSearch() {
    setView('search')
    setResponse(null)
    setError(null)
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

        {view === 'results' && response ? (
          <ResultsView response={response} onOpen={setSelectedCard} onNewSearch={handleNewSearch} />
        ) : null}
      </main>

      {selectedCard ? <RecipeDetail card={selectedCard} onClose={() => setSelectedCard(null)} /> : null}
    </>
  )
}

function ResultsView({ response, onOpen, onNewSearch }) {
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
      </div>

      {response.pantry_unresolved.length > 0 ? (
        <p style={{ fontSize: 13, color: 'var(--color-warning)', margin: 0 }}>
          Not recognized and not used in this search: {response.pantry_unresolved.join(', ')}
        </p>
      ) : null}

      {!hasExact ? <ClosestMatchNotice hasExactMatches={false} /> : null}

      <RecipeGrid cards={cardsToShow} onOpen={onOpen} />
    </div>
  )
}
