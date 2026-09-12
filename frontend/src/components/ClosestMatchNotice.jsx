import '../styles/panels.css'

export function ClosestMatchNotice({ hasExactMatches }) {
  return (
    <div className="card closest-match-notice">
      <span className="closest-match-notice__icon" aria-hidden="true">
        ℹ️
      </span>
      <div>
        <p className="closest-match-notice__title">
          {hasExactMatches ? 'No exact matches within your target?' : 'No exact matches found — here are the closest options.'}
        </p>
        <p className="closest-match-notice__body">
          We&rsquo;ve also included the closest options. Some recipes may take a little longer or cost a little more.
        </p>
      </div>
    </div>
  )
}
