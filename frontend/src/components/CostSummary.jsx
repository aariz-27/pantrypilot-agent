export function CostSummary({ card }) {
  const incompleteCount = card.missing_ingredients.filter((row) => !row.price_complete).length

  return (
    <div className="card" style={{ padding: 'var(--space-4)' }}>
      {card.price_complete && card.estimated_additional_spend_aed !== null ? (
        <p style={{ margin: 0, fontWeight: 700, fontSize: 16 }}>
          Estimated additional spend: AED {card.estimated_additional_spend_aed.toFixed(2)}
        </p>
      ) : (
        <>
          <p style={{ margin: 0, fontWeight: 700, fontSize: 16, color: 'var(--color-warning)' }}>
            Estimated additional spend unavailable
          </p>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--color-text-muted)' }}>
            Price estimate incomplete for {incompleteCount} ingredient{incompleteCount === 1 ? '' : 's'}.
          </p>
        </>
      )}
      <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--color-text-subtle)' }}>
        Estimates use PantryPilot reference grocery prices. Actual store prices may vary.
      </p>
    </div>
  )
}
