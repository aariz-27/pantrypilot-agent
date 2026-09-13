import { useEffect, useState } from 'react'
import { getDashboardSummary } from '../services/adminApi.js'

const METRICS = [
  { key: 'effective_ingredient_count', label: 'Effective ingredients (built-in + admin)' },
  { key: 'canonical_ingredient_count', label: 'Admin-managed ingredients' },
  { key: 'active_alias_count', label: 'Active aliases' },
  { key: 'ingredients_with_manual_price', label: 'Ingredients with manual price' },
  { key: 'ingredients_without_known_price', label: 'Ingredients without known price' },
  { key: 'mapped_product_count', label: 'Mapped grocery products' },
  { key: 'unmapped_product_count', label: 'Unmapped grocery products' },
]

export function AdminDashboard() {
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    getDashboardSummary()
      .then((data) => {
        if (!cancelled) setSummary(data)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div>
      <h1 className="admin-page-title">Dashboard</h1>
      {error ? (
        <p className="field-error">{error}</p>
      ) : !summary ? (
        <p className="admin-muted">Loading…</p>
      ) : (
        <div className="admin-metric-grid">
          {METRICS.map((metric) => (
            <div key={metric.key} className="card admin-metric-card">
              <p className="admin-metric-card__value">{summary[metric.key]}</p>
              <p className="admin-metric-card__label">{metric.label}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
