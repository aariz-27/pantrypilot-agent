// Safe, user-facing error surface -- never renders exception internals,
// stack traces, or provider payloads (docs/AGENTS.md security section).
export function ErrorState({ message, retryable, onRetry }) {
  return (
    <div className="card" role="alert" style={{ padding: 'var(--space-5)', textAlign: 'center' }}>
      <p style={{ margin: '0 0 var(--space-3)', fontWeight: 700, color: 'var(--color-danger)' }}>
        {message || 'Something went wrong. Please try again.'}
      </p>
      {retryable && onRetry ? (
        <button type="button" className="btn btn-primary" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  )
}
