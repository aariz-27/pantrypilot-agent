import '../styles/panels.css'

// Safe, user-facing error surface -- never renders exception internals,
// stack traces, or provider payloads (docs/AGENTS.md security section).
export function ErrorState({ message, retryable, onRetry }) {
  return (
    <div className="card error-state" role="alert">
      <div className="error-state__icon" aria-hidden="true">
        ⚠️
      </div>
      <p className="error-state__message">{message || 'Something went wrong. Please try again.'}</p>
      {retryable && onRetry ? (
        <button type="button" className="btn btn-primary" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  )
}
