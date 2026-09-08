export function ClosestMatchNotice({ hasExactMatches }) {
  return (
    <div className="card" style={{ padding: 'var(--space-4)', display: 'flex', gap: 'var(--space-3)', alignItems: 'flex-start' }}>
      <span aria-hidden="true">ℹ️</span>
      <div>
        <p style={{ margin: 0, fontWeight: 700 }}>
          {hasExactMatches ? 'No exact matches within your target?' : 'No exact matches found — here are the closest options.'}
        </p>
        <p style={{ margin: '4px 0 0', color: 'var(--color-text-muted)', fontSize: 13 }}>
          We&rsquo;ve also included the closest options. Some recipes may take a little longer or cost a little more.
        </p>
      </div>
    </div>
  )
}
