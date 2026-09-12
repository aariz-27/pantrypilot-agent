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

  const matchBadge = <span className="badge badge-success recipe-card__match-badge">★ {matchPercent}% pantry match</span>
  const timeBadge =
    card.total_time_minutes !== null ? <span className="recipe-card__time-badge">⏱ {card.total_time_minutes} min</span> : null
  // Read-only indicator, not a control -- saving/unsaving only happens
  // from the detail view, so this never nests a second interactive
  // button inside the card's own button element.
  const savedBadge = saved ? (
    <span className="recipe-card__saved-badge" aria-label="Saved to your recipes">
      ★ Saved
    </span>
  ) : null

  return (
    <button type="button" className="card recipe-card" onClick={() => onOpen(card)}>
      {imageUrl ? (
        <div className="recipe-card__media">
          <img src={imageUrl} alt={card.name} />
          {matchBadge}
          {timeBadge}
          {savedBadge}
        </div>
      ) : (
        // No provider image_url -- render no image block/frame/placeholder
        // at all (never a fabricated photo), just the same match/time/
        // saved information as a plain badge row so nothing is lost.
        <div className="recipe-card__badges-row">
          {matchBadge}
          {timeBadge}
          {savedBadge}
        </div>
      )}

      <div className="recipe-card__body">
        <div className="recipe-card__tags">
          <span className="badge badge-success">{DIFFICULTY_LABEL[card.difficulty]}</span>
          {card.cuisine ? <span className="badge badge-neutral">{card.cuisine}</span> : null}
          {/* PR #15 second correction pass (2026-09-08): a reserve card
              only ever appears here when the search's active anchor's
              own matching pool was exhausted -- never presented as an
              equally strong match. */}
          {card.contains_active_anchor === false ? <span className="badge badge-warning">Alternative pick</span> : null}
        </div>

        <h3 className="recipe-card__title">{card.name}</h3>

        {!card.is_exact_match && card.deviation_reasons.length ? (
          <p className="recipe-card__deviation">{card.deviation_reasons.join(' · ')}</p>
        ) : null}

        <div className="recipe-card__match">
          <p className="recipe-card__match-label">{matchPercent}% pantry match</p>
          <div className="recipe-card__progress-track">
            <div className="recipe-card__progress-fill" style={{ width: `${matchPercent}%` }} />
          </div>
        </div>

        <div className="recipe-card__meta-row">
          <span className="recipe-card__meta-row--matched">✓ {matchedCount} in your pantry</span>
          <span className="recipe-card__meta-row--missing">✕ {missingCount} missing</span>
        </div>

        <CostLabel card={card} />

        <span className="btn btn-secondary recipe-card__cta">View recipe</span>
      </div>
    </button>
  )
}
