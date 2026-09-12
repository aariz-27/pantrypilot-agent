import '../styles/panels.css'

export function IngredientStatusList({ card, onMarkHave, onMarkHaveUnresolved }) {
  return (
    <div>
      <div className="ingredient-status-list__legend">
        <span>✓ In your pantry</span>
        <span>✕ Missing</span>
        {card.unresolved_ingredients.length ? <span>◐ Uncertain</span> : null}
      </div>

      <h3 className="ingredient-status-list__group-title">You already have</h3>
      <ul className="ingredient-status-list__list">
        {card.matched_ingredients.map((name) => (
          <li key={name} className="ingredient-status-list__row ingredient-status-list__row--have">
            ✓ {name}
          </li>
        ))}
        {card.matched_ingredients.length === 0 ? (
          <li className="ingredient-status-list__row--empty">None of this recipe&rsquo;s ingredients are in your pantry yet.</li>
        ) : null}
      </ul>

      <h3 className="ingredient-status-list__group-title">You need</h3>
      <ul
        className={`ingredient-status-list__list${card.unresolved_ingredients.length ? '' : ' ingredient-status-list__list--tight'}`}
      >
        {card.missing_ingredients.map((row) => (
          <li
            key={`${row.canonical_id ?? row.raw_name}`}
            className="ingredient-status-list__row ingredient-status-list__row--missing"
          >
            <span>✕ {row.display_name}</span>
            <span className="ingredient-status-list__row-meta">
              <span className="ingredient-status-list__price">
                {row.price_complete && row.estimated_cost_aed !== null
                  ? `Est. AED ${row.estimated_cost_aed.toFixed(2)}`
                  : 'Price unavailable'}
              </span>
              {/* Only a recognized/canonical missing ingredient may ever
                  be marked "have" -- an unresolved raw term (no
                  canonical_id) is never trusted through this control
                  (ticket section 2). */}
              {row.canonical_id && onMarkHave ? (
                <label className="ingredient-status-list__have-checkbox">
                  <input
                    type="checkbox"
                    onChange={() => onMarkHave(row.canonical_id)}
                    aria-label={`I have ${row.display_name}`}
                  />
                  I have this
                </label>
              ) : null}
            </span>
          </li>
        ))}
        {card.missing_ingredients.length === 0 ? (
          <li className="ingredient-status-list__row--empty">Nothing missing -- you have everything for this recipe.</li>
        ) : null}
      </ul>

      {card.unresolved_ingredients.length ? (
        <>
          <h3 className="ingredient-status-list__group-title">Uncertain</h3>
          <ul className="ingredient-status-list__list ingredient-status-list__list--tight">
            {card.unresolved_ingredients.map((row) => (
              <li
                key={row.identity_key || row.raw_name}
                className="ingredient-status-list__row ingredient-status-list__row--uncertain"
              >
                <span>◐ {row.display_name}</span>
                {/* Priority 3 (ticket, PR #15 correction pass): the user
                    may genuinely own this even though PantryPilot could
                    not normalize it -- confirming it never assigns a
                    canonical_id or promotes it into the taxonomy/pricing
                    tables; it only records the user's own raw pantry
                    state for this session. */}
                {onMarkHaveUnresolved ? (
                  <label className="ingredient-status-list__have-checkbox">
                    <input
                      type="checkbox"
                      onChange={() => onMarkHaveUnresolved(row.identity_key, row.raw_name)}
                      aria-label={`I have ${row.display_name}`}
                    />
                    I have this
                  </label>
                ) : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  )
}
