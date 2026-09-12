import '../styles/panels.css'

export function CostSummary({ card }) {
  const incompleteCount = card.missing_ingredients.filter((row) => !row.price_complete).length

  return (
    <div className="card cost-summary">
      {card.price_complete && card.estimated_additional_spend_aed !== null ? (
        <p className="cost-summary__headline">
          Estimated additional spend: AED {card.estimated_additional_spend_aed.toFixed(2)}
        </p>
      ) : (
        <>
          <p className="cost-summary__headline cost-summary__headline--warning">Estimated additional spend unavailable</p>
          <p className="cost-summary__note">
            Price estimate incomplete for {incompleteCount} ingredient{incompleteCount === 1 ? '' : 's'}.
          </p>
        </>
      )}
      <p className="cost-summary__disclaimer">
        Estimates use PantryPilot reference grocery prices. Actual store prices may vary.
      </p>
    </div>
  )
}
