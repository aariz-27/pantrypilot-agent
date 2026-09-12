import { useState } from 'react'
import { login } from '../services/adminApi.js'

export function AdminLogin({ onLoginSuccess }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const session = await login(username, password)
      onLoginSuccess(session)
    } catch (err) {
      // Same generic message regardless of backend detail -- the
      // backend itself already never distinguishes bad username from
      // bad password (ADMIN_UNAUTHORIZED either way).
      setError(err.code === 'RATE_LIMITED' ? err.message : 'Invalid username or password.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="admin-login-screen">
      <form className="admin-login-card" onSubmit={handleSubmit}>
        <h1 className="admin-login-title">PantryPilot Admin</h1>
        <p className="admin-login-subtitle">Sign in to manage ingredients, aliases, and pricing.</p>

        <label className="field-label" htmlFor="admin-username">
          Username
        </label>
        <input
          id="admin-username"
          className="field-input"
          type="text"
          name="username"
          autoComplete="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
          autoFocus
        />

        <label className="field-label" htmlFor="admin-password">
          Password
        </label>
        <input
          id="admin-password"
          className="field-input"
          type="password"
          name="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />

        {error ? (
          <p className="field-error admin-login-error" role="alert">
            {error}
          </p>
        ) : null}

        <button type="submit" className="btn btn-primary admin-login-submit" disabled={submitting}>
          {submitting ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}
