import { ThemeToggle } from './ThemeToggle'
import './Header.css'

export function Header({ onBrandClick }) {
  return (
    <header className="app-header">
      <div className="container app-header__inner">
        <button type="button" className="app-header__brand" onClick={onBrandClick}>
          <span className="app-header__logo" aria-hidden="true">
            🍲
          </span>
          PantryPilot
        </button>
        <div className="app-header__actions">
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
