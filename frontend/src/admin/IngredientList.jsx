import { useCallback, useEffect, useState } from 'react'
import { createIngredient, listEffectiveCatalog } from '../services/adminApi.js'
import { useDebouncedValue } from '../hooks/useDebouncedValue.js'

const PAGE_SIZE = 25

// 2026-09-13 admin completion ticket: this list now reads the EFFECTIVE
// catalog (built-in app.domain.grocery_taxonomy vocabulary + admin-
// managed ingredients, merged exactly as the live app resolves them --
// app.repositories.runtime_ingredient_repository.get_merged_vocabulary)
// rather than only admin-created rows. "Add ingredient" still creates
// an admin-managed override via the unchanged admin-only endpoint; a
// built-in row is browsed/priced here but not edited (there is nothing
// to edit -- it is not a database row).
export function IngredientList({ onOpenIngredient, priceFocusMode = false }) {
  const [query, setQuery] = useState('')
  const debouncedQuery = useDebouncedValue(query, 250)
  const [page, setPage] = useState(1)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [showCreateForm, setShowCreateForm] = useState(false)

  // Reset to page 1 whenever the filters change -- derived during
  // render (React's documented "adjusting state when a prop changes"
  // pattern) rather than via a dedicated effect, so a filter change
  // and the resulting page reset land in the same render pass instead
  // of triggering an extra one.
  const [appliedFilters, setAppliedFilters] = useState([debouncedQuery])
  if (appliedFilters[0] !== debouncedQuery) {
    setAppliedFilters([debouncedQuery])
    setPage(1)
  }

  const refresh = useCallback(() => {
    listEffectiveCatalog({ q: debouncedQuery || undefined, page, pageSize: PAGE_SIZE })
      .then((data) => {
        setError(null)
        setResult(data)
      })
      .catch((err) => setError(err.message))
  }, [debouncedQuery, page])

  useEffect(() => {
    refresh()
  }, [refresh])

  const items = priceFocusMode
    ? (result?.items ?? []).filter((item) => !item.has_manual_price && !item.has_reference_price)
    : (result?.items ?? [])

  return (
    <div>
      <div className="admin-page-header">
        <h1 className="admin-page-title">{priceFocusMode ? 'Prices — ingredients missing a known price' : 'Ingredients'}</h1>
        {!priceFocusMode ? (
          <button type="button" className="btn btn-primary" onClick={() => setShowCreateForm((v) => !v)}>
            {showCreateForm ? 'Cancel' : 'Add ingredient'}
          </button>
        ) : null}
      </div>

      {showCreateForm ? (
        <CreateIngredientForm
          onCreated={() => {
            setShowCreateForm(false)
            refresh()
          }}
        />
      ) : null}

      <div className="admin-toolbar">
        <input
          className="field-input"
          type="search"
          placeholder="Search by name or alias…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search ingredients"
        />
      </div>

      {error ? <p className="field-error">{error}</p> : null}

      <table className="admin-table">
        <thead>
          <tr>
            <th>Canonical ID</th>
            <th>Display name</th>
            <th>Source</th>
            <th>Aliases</th>
            <th>Price</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.canonical_id}>
              <td>
                <code>{item.canonical_id}</code>
              </td>
              <td>{item.display_name}</td>
              <td>
                <span className={`badge ${item.source === 'admin' ? 'badge-success' : 'badge-neutral'}`}>
                  {item.source === 'admin' ? 'Admin' : 'Built-in'}
                </span>
              </td>
              <td>{item.alias_count}</td>
              <td>
                {item.has_manual_price || item.has_reference_price ? (
                  <span className="badge badge-success">Priced</span>
                ) : (
                  <span className="badge badge-warning">No price</span>
                )}
              </td>
              <td>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => onOpenIngredient(item.canonical_id, item.source)}
                >
                  Manage
                </button>
              </td>
            </tr>
          ))}
          {items.length === 0 && result ? (
            <tr>
              <td colSpan={6} className="admin-empty-row">
                No ingredients found.
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>

      {!priceFocusMode && result ? (
        <div className="admin-pagination">
          <button type="button" className="btn btn-secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            Previous
          </button>
          <span className="admin-muted">
            Page {page} of {Math.max(1, Math.ceil(result.total / PAGE_SIZE))} ({result.total} total)
          </span>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={page * PAGE_SIZE >= result.total}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </button>
        </div>
      ) : null}
    </div>
  )
}

function CreateIngredientForm({ onCreated }) {
  const [canonicalId, setCanonicalId] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [defaultUnit, setDefaultUnit] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await createIngredient({ canonical_id: canonicalId, display_name: displayName, default_unit: defaultUnit || null })
      setCanonicalId('')
      setDisplayName('')
      setDefaultUnit('')
      onCreated()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="card admin-form" onSubmit={handleSubmit}>
      <div className="admin-form__row">
        <label className="field-label" htmlFor="new-canonical-id">
          Canonical ID
        </label>
        <input
          id="new-canonical-id"
          className="field-input"
          value={canonicalId}
          onChange={(e) => setCanonicalId(e.target.value)}
          placeholder="e.g. bell_pepper"
          required
        />
        <p className="field-help">Lowercase snake_case. Cannot be changed after creation.</p>
      </div>
      <div className="admin-form__row">
        <label className="field-label" htmlFor="new-display-name">
          Display name
        </label>
        <input
          id="new-display-name"
          className="field-input"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder="e.g. Bell Pepper"
          required
        />
      </div>
      <div className="admin-form__row">
        <label className="field-label" htmlFor="new-default-unit">
          Default unit (optional)
        </label>
        <input
          id="new-default-unit"
          className="field-input"
          value={defaultUnit}
          onChange={(e) => setDefaultUnit(e.target.value)}
          placeholder="e.g. g"
        />
      </div>
      {error ? <p className="field-error">{error}</p> : null}
      <button type="submit" className="btn btn-primary" disabled={submitting}>
        {submitting ? 'Creating…' : 'Create ingredient'}
      </button>
    </form>
  )
}
