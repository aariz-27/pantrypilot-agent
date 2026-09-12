import { useEffect, useState } from 'react'
import { listGroceryProducts } from '../services/adminApi.js'
import { useDebouncedValue } from '../hooks/useDebouncedValue.js'

const PAGE_SIZE = 25
const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'mapped', label: 'Mapped' },
  { value: 'unmapped_ingredient', label: 'Unmapped ingredient' },
  { value: 'filtered_out', label: 'Filtered out' },
  { value: 'unparseable_price', label: 'Unparseable price' },
  { value: 'unparseable_package', label: 'Unparseable package' },
  { value: 'unsupported_unit', label: 'Unsupported unit' },
  { value: 'duplicate', label: 'Duplicate' },
]

export function GroceryProducts() {
  const [query, setQuery] = useState('')
  const debouncedQuery = useDebouncedValue(query, 250)
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  // See IngredientList.jsx for why this resets page during render
  // rather than via a dedicated effect.
  const [appliedFilters, setAppliedFilters] = useState([debouncedQuery, status])
  if (appliedFilters[0] !== debouncedQuery || appliedFilters[1] !== status) {
    setAppliedFilters([debouncedQuery, status])
    setPage(1)
  }

  useEffect(() => {
    listGroceryProducts({ q: debouncedQuery || undefined, status: status || undefined, page, pageSize: PAGE_SIZE })
      .then((data) => {
        setError(null)
        setResult(data)
      })
      .catch((err) => setError(err.message))
  }, [debouncedQuery, status, page])

  return (
    <div>
      <h1 className="admin-page-title">Data mapping</h1>
      <p className="field-help">
        Read-only inspection of raw grocery import records and their mapping outcome. No bulk remapping is available here.
      </p>

      <div className="admin-toolbar">
        <input
          className="field-input"
          type="search"
          placeholder="Search by product title…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search grocery products"
        />
        <select className="field-select" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Filter by mapping status">
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {error ? <p className="field-error">{error}</p> : null}

      <div className="admin-table-scroller">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Brand</th>
              <th>Canonical ID</th>
              <th>Status</th>
              <th>Reason</th>
              <th>Price / unit</th>
            </tr>
          </thead>
          <tbody>
            {(result?.items ?? []).map((product) => (
              <tr key={product.id}>
                <td>{product.title}</td>
                <td>{product.brand ?? '—'}</td>
                <td>{product.canonical_id ? <code>{product.canonical_id}</code> : '—'}</td>
                <td>
                  <span className={`badge ${product.mapping_status === 'mapped' ? 'badge-success' : 'badge-neutral'}`}>
                    {product.mapping_status}
                  </span>
                </td>
                <td>{product.rejection_reason ?? '—'}</td>
                <td>
                  {product.normalized_price_per_unit != null
                    ? `${product.normalized_price_per_unit} / ${product.normalized_unit}`
                    : '—'}
                </td>
              </tr>
            ))}
            {result && result.items.length === 0 ? (
              <tr>
                <td colSpan={6} className="admin-empty-row">
                  No products found.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      {result ? (
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
