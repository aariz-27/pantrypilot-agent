export function EmptyState({ onNewSearch }) {
  return (
    <div className="card" style={{ padding: 'var(--space-7)', textAlign: 'center' }}>
      <div style={{ fontSize: 40, marginBottom: 'var(--space-3)' }} aria-hidden="true">
        🔍
      </div>
      <h2 style={{ margin: '0 0 var(--space-2)' }}>No exact matches found</h2>
      <p style={{ color: 'var(--color-text-muted)', maxWidth: 420, margin: '0 auto var(--space-4)' }}>
        We couldn&rsquo;t find any recipes that match your criteria closely enough to show, even with some flexibility on
        time or budget.
      </p>
      <button type="button" className="btn btn-primary" onClick={onNewSearch}>
        Try a new search
      </button>
    </div>
  )
}
