import { useEffect, useId, useRef } from 'react'
import { IngredientStatusList } from './IngredientStatusList'
import { CostSummary } from './CostSummary'
import { safeHttpUrl } from '../utils/safeUrl'
import './RecipeDetail.css'

const DIFFICULTY_LABEL = { easy: 'Easy', medium: 'Medium', hard: 'Hard', unknown: 'Unknown' }

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

function getFocusableElements(container) {
  return Array.from(container.querySelectorAll(FOCUSABLE_SELECTOR))
}

function Steps({ instructions }) {
  if (!instructions) return null
  // Rendering choice only -- the underlying grounded text is never
  // rewritten. Multiple non-empty lines render as a numbered list;
  // a single block renders faithfully as-is (ticket section 25).
  const lines = instructions
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)

  if (lines.length > 1) {
    return (
      <ol className="recipe-detail__instructions" style={{ paddingLeft: 20 }}>
        {lines.map((line, index) => (
          <li key={index}>{line}</li>
        ))}
      </ol>
    )
  }
  return <p className="recipe-detail__instructions">{instructions}</p>
}

export function RecipeDetail({ card, onClose }) {
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
      // Focus trap: Tab/Shift+Tab must cycle only within the dialog,
      // never escape to the page behind it (WAI-ARIA dialog pattern).
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

  // Serving-scaling uncertainty (post-review fix, 2026-09-08):
  // provider_original_servings is null/non-positive exactly when the
  // backend could not determine a reliable original serving count to
  // scale from (app.domain.serving_scaler.scale_recipe_servings only
  // ever returns scaling_applied=False in that situation). In that
  // case, the grounded ingredient quantities are NOT known to serve
  // the requested count -- showing "Serves N" would imply a precision
  // the data doesn't have, so this shows an explicit uncertainty state
  // instead. When the original count IS known, quantities are either
  // genuinely rescaled or already exactly correct -- both are reliable,
  // so normal "Serves N" applies in either case.
  const scalingUncertain = !(card.provider_original_servings > 0)
  const servingsLabel = scalingUncertain
    ? `Requested: ${card.requested_servings} servings · quantity scaling unavailable`
    : `Serves ${card.requested_servings}`

  const subline = [DIFFICULTY_LABEL[card.difficulty], card.cuisine].filter(Boolean).join(' · ')
  const imageUrl = safeHttpUrl(card.image_url)
  const sourceUrl = safeHttpUrl(card.source_url)

  return (
    <div className="recipe-detail__overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="recipe-detail" role="dialog" aria-modal="true" aria-labelledby={titleId} ref={dialogRef}>
        <div className="recipe-detail__header">
          <button type="button" className="btn-icon" onClick={onClose} ref={closeButtonRef} aria-label="Back to results">
            <span aria-hidden="true">←</span>
          </button>
          <strong>Back to results</strong>
        </div>

        <div className="recipe-detail__media">
          {imageUrl ? (
            <img src={imageUrl} alt={card.name} />
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--color-text-subtle)' }}>
              No image available
            </div>
          )}
        </div>

        <div className="recipe-detail__body">
          <div>
            <h2 id={titleId} className="recipe-detail__title">
              {card.name}
            </h2>
            <p className="recipe-detail__subline">{subline}</p>
            <p
              className="recipe-detail__subline"
              style={scalingUncertain ? { color: 'var(--color-warning)', fontWeight: 600 } : undefined}
            >
              {servingsLabel}
            </p>
          </div>

          <div className="recipe-detail__time-group">
            <div className="recipe-detail__time-item">
              <strong>{card.prep_time_minutes ?? '—'} min</strong>
              <span>Prep</span>
            </div>
            <div className="recipe-detail__time-item">
              <strong>{card.cook_time_minutes ?? '—'} min</strong>
              <span>Cook</span>
            </div>
            <div className="recipe-detail__time-item">
              <strong>{card.total_time_minutes ?? '—'} min</strong>
              <span>Total</span>
            </div>
          </div>

          <div className="card" style={{ padding: 'var(--space-4)' }}>
            <p style={{ margin: '0 0 var(--space-2)', fontWeight: 700 }}>
              {card.matched_ingredients.length} of {card.matched_ingredients.length + card.missing_ingredients.length} ingredients available
            </p>
            <div className="recipe-card__progress-track">
              <div className="recipe-card__progress-fill" style={{ width: `${Math.round(card.pantry_coverage * 100)}%` }} />
            </div>
          </div>

          <IngredientStatusList card={card} />

          <CostSummary card={card} />

          <div>
            <h3 style={{ fontSize: 16 }}>Steps</h3>
            <Steps instructions={card.instructions} />
          </div>

          {sourceUrl ? (
            <a href={sourceUrl} target="_blank" rel="noreferrer" className="btn btn-secondary" style={{ alignSelf: 'flex-start' }}>
              View Original Recipe
            </a>
          ) : null}
        </div>
      </div>
    </div>
  )
}
