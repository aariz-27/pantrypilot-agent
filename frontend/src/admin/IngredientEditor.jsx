import { useCallback, useEffect, useState } from 'react'
import {
  createAlias,
  createManualPrice,
  deactivateAlias,
  deactivateManualPrice,
  getIngredient,
  getIngredientPrices,
  listAliases,
  reassignAlias,
  updateIngredient,
  updateManualPrice,
} from '../services/adminApi.js'
import { ConfirmDialog } from './ConfirmDialog.jsx'

const NORMALIZED_UNITS = ['g', 'ml', 'pcs']

export function IngredientEditor({ canonicalId, onClose }) {
  const [ingredient, setIngredient] = useState(null)
  const [error, setError] = useState(null)

  const refresh = useCallback(() => {
    getIngredient(canonicalId)
      .then((data) => {
        setError(null)
        setIngredient(data)
      })
      .catch((err) => setError(err.message))
  }, [canonicalId])

  useEffect(() => {
    refresh()
  }, [refresh])

  return (
    <div>
      <div className="admin-page-header">
        <button type="button" className="btn-icon" onClick={onClose} aria-label="Back to ingredient list">
          ←
        </button>
        <h1 className="admin-page-title">{ingredient ? ingredient.display_name : canonicalId}</h1>
      </div>

      {error ? <p className="field-error">{error}</p> : null}

      {ingredient ? (
        <>
          <OverviewSection ingredient={ingredient} onUpdated={refresh} />
          <AliasesSection canonicalId={canonicalId} />
          <PricingSection canonicalId={canonicalId} />
        </>
      ) : !error ? (
        <p className="admin-muted">Loading…</p>
      ) : null}
    </div>
  )
}

function OverviewSection({ ingredient, onUpdated }) {
  const [displayName, setDisplayName] = useState(ingredient.display_name)
  const [defaultUnit, setDefaultUnit] = useState(ingredient.default_unit ?? '')
  const [status, setStatus] = useState(ingredient.status)
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  async function handleSave(event) {
    event.preventDefault()
    setError(null)
    setSaved(false)
    setSubmitting(true)
    try {
      await updateIngredient(ingredient.canonical_id, {
        display_name: displayName,
        default_unit: defaultUnit || null,
        status,
      })
      setSaved(true)
      onUpdated()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="card admin-section">
      <h2 className="admin-section__title">Overview</h2>
      <form onSubmit={handleSave}>
        <div className="admin-form__row">
          <label className="field-label">Canonical ID</label>
          <input className="field-input" value={ingredient.canonical_id} disabled />
          <p className="field-help">Immutable -- referenced by aliases and prices.</p>
        </div>
        <div className="admin-form__row">
          <label className="field-label" htmlFor="edit-display-name">
            Display name
          </label>
          <input
            id="edit-display-name"
            className="field-input"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            required
          />
        </div>
        <div className="admin-form__row">
          <label className="field-label" htmlFor="edit-default-unit">
            Default unit
          </label>
          <input id="edit-default-unit" className="field-input" value={defaultUnit} onChange={(e) => setDefaultUnit(e.target.value)} />
        </div>
        <div className="admin-form__row">
          <label className="field-label" htmlFor="edit-status">
            Status
          </label>
          <select id="edit-status" className="field-select" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="active">Active</option>
            <option value="archived">Archived</option>
          </select>
        </div>
        {error ? <p className="field-error">{error}</p> : null}
        {saved ? <p className="admin-success-text">Saved.</p> : null}
        <button type="submit" className="btn btn-primary" disabled={submitting}>
          {submitting ? 'Saving…' : 'Save changes'}
        </button>
      </form>
    </section>
  )
}

function AliasesSection({ canonicalId }) {
  const [aliases, setAliases] = useState(null)
  const [newAlias, setNewAlias] = useState('')
  const [error, setError] = useState(null)
  const [pendingDeactivate, setPendingDeactivate] = useState(null)
  const [reassigning, setReassigning] = useState(null) // { alias, target }

  const refresh = useCallback(() => {
    listAliases(canonicalId)
      .then(setAliases)
      .catch((err) => setError(err.message))
  }, [canonicalId])

  useEffect(() => {
    refresh()
  }, [refresh])

  async function handleAddAlias(event) {
    event.preventDefault()
    setError(null)
    try {
      await createAlias(canonicalId, newAlias)
      setNewAlias('')
      refresh()
    } catch (err) {
      setError(err.message)
    }
  }

  async function handleConfirmDeactivate() {
    const alias = pendingDeactivate
    setPendingDeactivate(null)
    try {
      await deactivateAlias(alias)
      refresh()
    } catch (err) {
      setError(err.message)
    }
  }

  async function handleReassignSubmit(event) {
    event.preventDefault()
    if (!reassigning?.target) return
    try {
      await reassignAlias(reassigning.alias, reassigning.target)
      setReassigning(null)
      refresh()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <section className="card admin-section">
      <h2 className="admin-section__title">Aliases</h2>
      <p className="field-help">
        A conflicting alias is never silently remapped -- reassigning an alias to a different ingredient requires explicit
        confirmation below.
      </p>
      <form className="admin-inline-form" onSubmit={handleAddAlias}>
        <input
          className="field-input"
          value={newAlias}
          onChange={(e) => setNewAlias(e.target.value)}
          placeholder="Add an alias, e.g. capsicum"
          required
        />
        <button type="submit" className="btn btn-secondary">
          Add alias
        </button>
      </form>
      {error ? <p className="field-error">{error}</p> : null}
      <ul className="admin-tag-list">
        {(aliases ?? []).map((alias) => (
          <li key={alias.alias} className="admin-tag">
            <span>{alias.alias}</span>
            <button
              type="button"
              className="admin-tag__reassign"
              onClick={() => setReassigning({ alias: alias.alias, target: '' })}
              aria-label={`Reassign alias ${alias.alias} to a different ingredient`}
            >
              Reassign
            </button>
            <button
              type="button"
              className="admin-tag__remove"
              onClick={() => setPendingDeactivate(alias.alias)}
              aria-label={`Remove alias ${alias.alias}`}
            >
              ×
            </button>
          </li>
        ))}
        {aliases && aliases.length === 0 ? <li className="admin-muted">No aliases yet.</li> : null}
      </ul>

      {reassigning ? (
        <form className="admin-inline-form admin-reassign-form" onSubmit={handleReassignSubmit}>
          <label className="field-label" htmlFor="reassign-target">
            Reassign "{reassigning.alias}" to canonical ID
          </label>
          <input
            id="reassign-target"
            className="field-input"
            value={reassigning.target}
            onChange={(e) => setReassigning({ ...reassigning, target: e.target.value })}
            required
          />
          <button type="submit" className="btn btn-primary">
            Confirm reassignment
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => setReassigning(null)}>
            Cancel
          </button>
        </form>
      ) : null}

      {pendingDeactivate ? (
        <ConfirmDialog
          title="Remove alias"
          message={`Deactivate the alias "${pendingDeactivate}"? It will no longer resolve to this ingredient.`}
          confirmLabel="Remove alias"
          onConfirm={handleConfirmDeactivate}
          onCancel={() => setPendingDeactivate(null)}
        />
      ) : null}
    </section>
  )
}

function PricingSection({ canonicalId }) {
  const [prices, setPrices] = useState(null)
  const [error, setError] = useState(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [pendingDeactivate, setPendingDeactivate] = useState(null)

  const refresh = useCallback(() => {
    getIngredientPrices(canonicalId)
      .then(setPrices)
      .catch((err) => setError(err.message))
  }, [canonicalId])

  useEffect(() => {
    refresh()
  }, [refresh])

  async function handleConfirmDeactivate() {
    const unit = pendingDeactivate
    setPendingDeactivate(null)
    try {
      await deactivateManualPrice(canonicalId, unit)
      refresh()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <section className="card admin-section">
      <div className="admin-page-header">
        <h2 className="admin-section__title">Pricing</h2>
        <button type="button" className="btn btn-secondary" onClick={() => setShowAddForm((v) => !v)}>
          {showAddForm ? 'Cancel' : 'Add manual price'}
        </button>
      </div>

      {error ? <p className="field-error">{error}</p> : null}

      <h3 className="admin-subsection-title">Reference price (from grocery import — read-only)</h3>
      {prices?.reference_prices.length ? (
        <table className="admin-table">
          <thead>
            <tr>
              <th>Unit</th>
              <th>Price / unit (AED)</th>
              <th>Contributors</th>
              <th>Source</th>
              <th>Collected</th>
            </tr>
          </thead>
          <tbody>
            {prices.reference_prices.map((p) => (
              <tr key={p.normalized_unit}>
                <td>{p.normalized_unit}</td>
                <td>{p.normalized_price_per_unit}</td>
                <td>{p.contributor_count}</td>
                <td>{p.source_name}</td>
                <td>{p.collected_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="admin-muted">No reference price available. This is not the same as a price of zero — unknown price is never reported as zero.</p>
      )}

      <h3 className="admin-subsection-title">Manual price entries (override, used when no reference price exists)</h3>
      {showAddForm ? (
        <ManualPriceForm
          canonicalId={canonicalId}
          onSaved={() => {
            setShowAddForm(false)
            refresh()
          }}
        />
      ) : null}
      {prices?.manual_prices.length ? (
        <table className="admin-table">
          <thead>
            <tr>
              <th>Unit</th>
              <th>Price / unit (AED)</th>
              <th>Provenance</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {prices.manual_prices.map((p) => (
              <ManualPriceRow
                key={p.normalized_unit}
                price={p}
                canonicalId={canonicalId}
                onUpdated={refresh}
                onDeactivate={() => setPendingDeactivate(p.normalized_unit)}
              />
            ))}
          </tbody>
        </table>
      ) : (
        <p className="admin-muted">No manual price entries.</p>
      )}

      {pendingDeactivate ? (
        <ConfirmDialog
          title="Remove manual price"
          message={`Deactivate the manual price entry for unit "${pendingDeactivate}"?`}
          confirmLabel="Remove price"
          onConfirm={handleConfirmDeactivate}
          onCancel={() => setPendingDeactivate(null)}
        />
      ) : null}
    </section>
  )
}

function ManualPriceRow({ price, canonicalId, onUpdated, onDeactivate }) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(String(price.normalized_price_per_unit))
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSave() {
    setError(null)
    setSubmitting(true)
    try {
      await updateManualPrice(canonicalId, price.normalized_unit, { normalized_price_per_unit: Number(value) })
      setEditing(false)
      onUpdated()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <tr>
      <td>{price.normalized_unit}</td>
      <td>
        {editing ? (
          <input
            className="field-input admin-inline-input"
            type="number"
            step="any"
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
        ) : (
          price.normalized_price_per_unit
        )}
        {error ? <p className="field-error">{error}</p> : null}
      </td>
      <td>{price.provenance_note}</td>
      <td className="admin-table__actions">
        {editing ? (
          <>
            <button type="button" className="btn btn-primary" onClick={handleSave} disabled={submitting}>
              Save
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </>
        ) : (
          <>
            <button type="button" className="btn btn-secondary" onClick={() => setEditing(true)}>
              Edit
            </button>
            <button type="button" className="admin-destructive-link" onClick={onDeactivate}>
              Remove
            </button>
          </>
        )}
      </td>
    </tr>
  )
}

function ManualPriceForm({ canonicalId, onSaved }) {
  const [normalizedUnit, setNormalizedUnit] = useState(NORMALIZED_UNITS[0])
  const [displayName, setDisplayName] = useState('')
  const [price, setPrice] = useState('')
  const [provenanceNote, setProvenanceNote] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await createManualPrice(canonicalId, {
        normalized_unit: normalizedUnit,
        display_name: displayName,
        normalized_price_per_unit: Number(price),
        provenance_note: provenanceNote,
      })
      onSaved()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="admin-form" onSubmit={handleSubmit}>
      <div className="admin-form__row">
        <label className="field-label" htmlFor="price-unit">
          Unit
        </label>
        <select id="price-unit" className="field-select" value={normalizedUnit} onChange={(e) => setNormalizedUnit(e.target.value)}>
          {NORMALIZED_UNITS.map((unit) => (
            <option key={unit} value={unit}>
              {unit}
            </option>
          ))}
        </select>
      </div>
      <div className="admin-form__row">
        <label className="field-label" htmlFor="price-display-name">
          Display name
        </label>
        <input id="price-display-name" className="field-input" value={displayName} onChange={(e) => setDisplayName(e.target.value)} required />
      </div>
      <div className="admin-form__row">
        <label className="field-label" htmlFor="price-value">
          Price per unit (AED)
        </label>
        <input
          id="price-value"
          className="field-input"
          type="number"
          step="any"
          min="0.0001"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
          required
        />
      </div>
      <div className="admin-form__row">
        <label className="field-label" htmlFor="price-provenance">
          Provenance note
        </label>
        <input
          id="price-provenance"
          className="field-input"
          value={provenanceNote}
          onChange={(e) => setProvenanceNote(e.target.value)}
          placeholder="e.g. Manually verified at LuLu Al Barsha, 2026-09-12"
          required
        />
      </div>
      {error ? <p className="field-error">{error}</p> : null}
      <button type="submit" className="btn btn-primary" disabled={submitting}>
        {submitting ? 'Saving…' : 'Save manual price'}
      </button>
    </form>
  )
}
