import { useEffect, useId, useRef } from 'react'
import { safeHttpUrl } from '../utils/safeUrl'
import './LocalDataPanel.css'

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

function getFocusableElements(container) {
  return Array.from(container.querySelectorAll(FOCUSABLE_SELECTOR))
}

function summarizeSearch(entry) {
  const pantryLabel = entry.pantryItems.length
    ? entry.pantryItems.map((item) => item.label).join(', ')
    : 'No ingredients'
  return pantryLabel
}

function formatTimestamp(ts) {
  try {
    return new Date(ts).toLocaleString()
  } catch {
    return ''
  }
}

// Everything this panel manages (ticket sections 5.3-5.5) is local,
// browser-only state -- no account, no server round trip. It's a
// self-contained dialog like RecipeDetail rather than a shared
// abstraction with it, on purpose: RecipeDetail's focus-trap behavior
// is already covered by its own tests, and duplicating ~20 lines here
// avoids risking a regression there for the sake of a one-off refactor.
export function LocalDataPanel({
  onClose,
  history,
  onRerunSearch,
  onClearHistory,
  saved,
  onRemoveSaved,
  onClearSaved,
  onClearPantry,
  onClearAll,
}) {
  const titleId = useId()
  const dialogRef = useRef(null)
  const closeButtonRef = useRef(null)
  const previouslyFocused = useRef(null)

  useEffect(() => {
    previouslyFocused.current = document.activeElement
    closeButtonRef.current?.focus()

    function handleKeyDown(event) {
      if (event.key === 'Escape') {
        onClose()
        return
      }
      if (event.key === 'Tab' && dialogRef.current) {
        const focusable = getFocusableElements(dialogRef.current)
        if (focusable.length === 0) return
        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault()
          last.focus()
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      if (previouslyFocused.current instanceof HTMLElement) {
        previouslyFocused.current.focus()
      }
    }
  }, [onClose])

  function handleClearAll() {
    if (window.confirm('Clear your pantry, search history, and saved recipes from this browser? This cannot be undone.')) {
      onClearAll()
    }
  }

  return (
    <div className="local-data-panel__overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="local-data-panel" role="dialog" aria-modal="true" aria-labelledby={titleId} ref={dialogRef}>
        <div className="local-data-panel__header">
          <h2 id={titleId} className="local-data-panel__title">
            Your data
          </h2>
          <button type="button" className="btn-icon" onClick={onClose} ref={closeButtonRef} aria-label="Close">
            <span aria-hidden="true">✕</span>
          </button>
        </div>

        <div className="local-data-panel__body">
          <p className="local-data-panel__intro">
            Everything here is stored only in this browser. Nothing is sent anywhere until you run a search.
          </p>

          <section>
            <div className="local-data-panel__section-header">
              <h3 className="local-data-panel__section-title">Recent searches</h3>
              {history.length > 0 ? (
                <button type="button" className="local-data-panel__link-btn" onClick={onClearHistory}>
                  Clear history
                </button>
              ) : null}
            </div>
            {history.length === 0 ? (
              <p className="local-data-panel__empty">No recent searches yet.</p>
            ) : (
              <ul className="local-data-panel__list">
                {history.map((entry, index) => (
                  <li key={`${entry.timestamp}-${index}`} className="local-data-panel__row">
                    <div className="local-data-panel__row-text">
                      <span className="local-data-panel__row-title">{summarizeSearch(entry)}</span>
                      <span className="local-data-panel__row-meta">
                        {entry.servings} servings · {entry.totalTimeMinutes} min
                        {entry.cuisine ? ` · ${entry.cuisine}` : ''} · {formatTimestamp(entry.timestamp)}
                      </span>
                    </div>
                    <button type="button" className="btn btn-secondary" onClick={() => onRerunSearch(entry)}>
                      Search again
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <div className="local-data-panel__section-header">
              <h3 className="local-data-panel__section-title">Saved recipes</h3>
              {saved.length > 0 ? (
                <button type="button" className="local-data-panel__link-btn" onClick={onClearSaved}>
                  Clear saved recipes
                </button>
              ) : null}
            </div>
            {saved.length === 0 ? (
              <p className="local-data-panel__empty">No saved recipes yet.</p>
            ) : (
              <ul className="local-data-panel__list">
                {saved.map((recipe) => {
                  const sourceUrl = safeHttpUrl(recipe.sourceUrl)
                  return (
                    <li key={recipe.recipeId} className="local-data-panel__row">
                      <div className="local-data-panel__row-text">
                        <span className="local-data-panel__row-title">{recipe.title}</span>
                        {sourceUrl ? (
                          <a href={sourceUrl} target="_blank" rel="noreferrer" className="local-data-panel__row-meta">
                            View recipe
                          </a>
                        ) : null}
                      </div>
                      <button type="button" className="btn btn-secondary" onClick={() => onRemoveSaved(recipe.recipeId)}>
                        Remove
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}
          </section>

          <section>
            <h3 className="local-data-panel__section-title local-data-panel__section-title--standalone">Reset</h3>
            <div className="local-data-panel__reset-row">
              <button type="button" className="btn btn-secondary" onClick={onClearPantry}>
                Clear current pantry
              </button>
              <button type="button" className="btn btn-secondary" onClick={handleClearAll}>
                Clear all local data
              </button>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
