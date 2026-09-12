import { ThemeToggle } from './ThemeToggle'
import './Header.css'

export function Header({ onBrandClick, onOpenLocalData }) {
  return (
    <header className="app-header">
      <div className="container-wide app-header__inner">
        <button type="button" className="app-header__brand" onClick={onBrandClick} aria-label="PantryPilot home">
          <span className="app-header__logo" aria-hidden="true">
            🍲
          </span>
          <span className="app-header__wordmark">
            PantryPilot
            <span className="app-header__tagline">Kitchen Intelligence</span>
          </span>
        </button>
        <div className="app-header__actions">
          {onOpenLocalData ? (
            <button
              type="button"
              className="btn-icon"
              onClick={onOpenLocalData}
              aria-label="Your data: recent searches, saved recipes, and reset"
            >
              <span aria-hidden="true">🔖</span>
            </button>
          ) : null}
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
