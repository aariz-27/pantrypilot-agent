export function IngredientStatusList({ card }) {
  return (
    <div>
      <div style={{ display: 'flex', gap: 'var(--space-4)', flexWrap: 'wrap', fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 'var(--space-3)' }}>
        <span>✓ In your pantry</span>
        <span>✕ Missing</span>
        {card.unresolved_ingredients.length ? <span>◐ Uncertain</span> : null}
      </div>

      <h3 style={{ fontSize: 14, margin: '0 0 var(--space-2)' }}>You already have</h3>
      <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 var(--space-4)', display: 'flex', flexDirection: 'column', gap: 6 }}>
        {card.matched_ingredients.map((name) => (
          <li key={name} style={{ color: 'var(--color-success)', fontWeight: 600, fontSize: 14 }}>
            ✓ {name}
          </li>
        ))}
        {card.matched_ingredients.length === 0 ? (
          <li style={{ color: 'var(--color-text-subtle)', fontSize: 13 }}>None of this recipe&rsquo;s ingredients are in your pantry yet.</li>
        ) : null}
      </ul>

      <h3 style={{ fontSize: 14, margin: '0 0 var(--space-2)' }}>You need</h3>
      <ul style={{ listStyle: 'none', padding: 0, margin: card.unresolved_ingredients.length ? '0 0 var(--space-4)' : 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
        {card.missing_ingredients.map((row) => (
          <li key={`${row.canonical_id ?? row.raw_name}`} style={{ color: 'var(--color-danger)', fontWeight: 600, fontSize: 14, display: 'flex', justifyContent: 'space-between', gap: 8 }}>
            <span>✕ {row.display_name}</span>
            <span style={{ fontWeight: 500 }}>
              {row.price_complete && row.estimated_cost_aed !== null
                ? `Est. AED ${row.estimated_cost_aed.toFixed(2)}`
                : 'Price unavailable'}
            </span>
          </li>
        ))}
        {card.missing_ingredients.length === 0 ? (
          <li style={{ color: 'var(--color-text-subtle)', fontSize: 13 }}>Nothing missing -- you have everything for this recipe.</li>
        ) : null}
      </ul>

      {card.unresolved_ingredients.length ? (
        <>
          <h3 style={{ fontSize: 14, margin: '0 0 var(--space-2)' }}>Uncertain</h3>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
            {card.unresolved_ingredients.map((name) => (
              <li key={name} style={{ color: 'var(--color-warning)', fontWeight: 600, fontSize: 14 }}>
                ◐ {name}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  )
}
