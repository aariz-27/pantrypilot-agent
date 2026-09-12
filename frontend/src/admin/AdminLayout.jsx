import { useState } from 'react'
import { logout } from '../services/adminApi.js'

const NAV_ITEMS = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'ingredients', label: 'Ingredients' },
  { key: 'prices', label: 'Prices' },
  { key: 'data_mapping', label: 'Data Mapping' },
  { key: 'audit', label: 'Audit' },
]

export function AdminLayout({ username, page, onNavigate, onLogout, children }) {
  const [loggingOut, setLoggingOut] = useState(false)

  async function handleLogout() {
    setLoggingOut(true)
    try {
      await logout()
    } catch {
      // Even if the network call fails, clear local state -- the
      // HttpOnly cookie's own expiry is the real backstop, and there is
      // no useful recovery action for the admin to take on failure here.
    } finally {
      setLoggingOut(false)
      onLogout()
    }
  }

  return (
    <div className="admin-shell">
      <aside className="admin-sidebar">
        <div className="admin-sidebar__brand">PantryPilot Admin</div>
        <nav className="admin-nav" aria-label="Admin navigation">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.key}
              type="button"
              className={`admin-nav__item${page === item.key ? ' admin-nav__item--active' : ''}`}
              onClick={() => onNavigate(item.key)}
              aria-current={page === item.key ? 'page' : undefined}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <div className="admin-sidebar__footer">
          <div className="admin-sidebar__user">{username}</div>
          <button type="button" className="btn btn-secondary admin-logout-btn" onClick={handleLogout} disabled={loggingOut}>
            {loggingOut ? 'Signing out…' : 'Log out'}
          </button>
        </div>
      </aside>
      <main className="admin-main">{children}</main>
    </div>
  )
}
