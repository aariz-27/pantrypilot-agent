import './IngredientChip.css'

export function IngredientChip({ label, unresolved = false, onRemove }) {
  return (
    <span className={`chip${unresolved ? ' chip--unresolved' : ''}`}>
      {label}
      {unresolved ? <span className="visually-hidden"> (unrecognized)</span> : null}
      <button type="button" className="chip__remove" onClick={onRemove} aria-label={`Remove ${label}`}>
        <span aria-hidden="true">×</span>
      </button>
    </span>
  )
}

export function IngredientChipList({ items, onRemove }) {
  if (!items.length) return null
  return (
    <div className="chip-list">
      {items.map((item) => (
        <IngredientChip
          key={item.id}
          label={item.label}
          unresolved={item.unresolved}
          onRemove={() => onRemove(item.id)}
        />
      ))}
    </div>
  )
}
