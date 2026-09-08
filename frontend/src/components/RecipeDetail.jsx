import { useEffect, useId, useRef } from 'react'
import { IngredientStatusList } from './IngredientStatusList'
import { CostSummary } from './CostSummary'
import { safeHttpUrl } from '../utils/safeUrl'
import './RecipeDetail.css'

const DIFFICULTY_LABEL = { easy: 'Easy', medium: 'Medium', hard: 'Hard', unknown: 'Unknown' }

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
  const closeButtonRef = useRef(null)
  const previouslyFocused = useRef(null)

  useEffect(() => {
    previouslyFocused.current = document.activeElement
    closeButtonRef.current?.focus()

    function handleKeyDown(event) {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      if (previouslyFocused.current instanceof HTMLElement) {
        previouslyFocused.current.focus()
      }
    }
  }, [onClose])

  const subline = [DIFFICULTY_LABEL[card.difficulty], card.cuisine, `Serves ${card.requested_servings}`]
    .filter(Boolean)
    .join(' · ')
  const imageUrl = safeHttpUrl(card.image_url)
  const sourceUrl = safeHttpUrl(card.source_url)

  return (
    <div className="recipe-detail__overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="recipe-detail" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="recipe-detail__header">
          <button type="button" className="btn-icon" onClick={onClose} ref={closeButtonRef} aria-label="Back to results">
            <span aria-hidden="true">←</span>
          </button>
          <strong>Back to results</strong>
        </div>

        <div className="recipe-detail__media">
          {imageUrl ? (
            <img src={imageUrl} alt="" />
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
