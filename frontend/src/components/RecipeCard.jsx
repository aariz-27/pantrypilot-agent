import { safeHttpUrl } from '../utils/safeUrl'
import './RecipeCard.css'

const DIFFICULTY_LABEL = { easy: 'Easy', medium: 'Medium', hard: 'Hard', unknown: 'Unknown' }

export function CostLabel({ card }) {
  if (!card.price_complete || card.estimated_additional_spend_aed === null) {
    return <span className="recipe-card__cost recipe-card__cost--unavailable">Estimated additional cost unavailable</span>
  }
  return <span className="recipe-card__cost">Est. additional cost: AED {card.estimated_additional_spend_aed.toFixed(2)}</span>
}

export function RecipeCard({ card, onOpen, saved }) {
  const matchedCount = card.matched_ingredients.length
  const missingCount = card.missing_ingredients.length
  const matchPercent = Math.round(card.pantry_coverage * 100)
  const imageUrl = safeHttpUrl(card.image_url)

  return (
    <button type="button" className="card recipe-card" onClick={() => onOpen(card)}>
      <div className="recipe-card__media">
        {imageUrl ? (
          <img src={imageUrl} alt={card.name} />
        ) : (
          <div className="recipe-card__no-image">
            <span aria-hidden="true" style={{ fontSize: 28 }}>
              🍽️
            </span>
            No image available
          </div>
        )}
        <span className="badge badge-success recipe-card__match-badge">★ {matchPercent}% pantry match</span>
        {card.total_time_minutes !== null ? (
          <span className="recipe-card__time-badge">⏱ {card.total_time_minutes} min</span>
        ) : null}
        {/* Read-only indicator, not a control -- saving/unsaving only
            happens from the detail view, so this never nests a second
            interactive button inside the card's own button element. */}
        {saved ? (
          <span className="recipe-card__saved-badge" aria-label="Saved to your recipes">
            ★ Saved
          </span>
        ) : null}
      </div>

      <div className="recipe-card__body">
        <div className="recipe-card__tags">
          <span className="badge badge-success">{DIFFICULTY_LABEL[card.difficulty]}</span>
          {card.cuisine ? <span className="badge badge-neutral">{card.cuisine}</span> : null}
          {/* PR #15 second correction pass (2026-09-08): a reserve card
              only ever appears here when the search's active anchor's
              own matching pool was exhausted -- never presented as an
              equally strong match. */}
          {card.contains_active_anchor === false ? (
            <span className="badge" style={{ background: 'var(--color-warning-soft)', color: 'var(--color-warning)' }}>
              Alternative pick
            </span>
          ) : null}
        </div>

        <h3 className="recipe-card__title">{card.name}</h3>

        {!card.is_exact_match && card.deviation_reasons.length ? (
          <p className="recipe-card__deviation">{card.deviation_reasons.join(' · ')}</p>
        ) : null}

        <div>
          <p style={{ margin: '0 0 6px', fontSize: 13, fontWeight: 600 }}>{matchPercent}% pantry match</p>
          <div className="recipe-card__progress-track">
            <div className="recipe-card__progress-fill" style={{ width: `${matchPercent}%` }} />
          </div>
        </div>

        <div className="recipe-card__meta-row">
          <span className="recipe-card__meta-row--matched">✓ {matchedCount} in your pantry</span>
          <span className="recipe-card__meta-row--missing">✕ {missingCount} missing</span>
        </div>

        <CostLabel card={card} />

        <span className="btn btn-secondary" style={{ marginTop: 4 }}>
          View recipe
        </span>
      </div>
    </button>
  )
}
