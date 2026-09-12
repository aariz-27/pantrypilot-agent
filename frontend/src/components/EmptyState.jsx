import '../styles/panels.css'

export function EmptyState({ onNewSearch }) {
  return (
    <div className="card empty-state">
      <div className="empty-state__icon" aria-hidden="true">
        🔍
      </div>
      <h2 className="empty-state__title">No exact matches found</h2>
      <p className="empty-state__body">
        We couldn&rsquo;t find any recipes that match your criteria closely enough to show, even with some flexibility on
        time or budget.
      </p>
      <button type="button" className="btn btn-primary" onClick={onNewSearch}>
        Try a new search
      </button>
    </div>
  )
}
