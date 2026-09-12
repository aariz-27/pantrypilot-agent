import { useEffect, useState } from 'react'
import { listAuditEntries } from '../services/adminApi.js'

const PAGE_SIZE = 25

export function AuditLog() {
  const [page, setPage] = useState(1)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    listAuditEntries({ page, pageSize: PAGE_SIZE })
      .then(setResult)
      .catch((err) => setError(err.message))
  }, [page])

  return (
    <div>
      <h1 className="admin-page-title">Audit log</h1>
      {error ? <p className="field-error">{error}</p> : null}

      <table className="admin-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>Admin</th>
            <th>Action</th>
            <th>Entity</th>
            <th>Summary</th>
          </tr>
        </thead>
        <tbody>
          {(result?.items ?? []).map((entry) => (
            <tr key={entry.id}>
              <td>{entry.occurred_at}</td>
              <td>{entry.admin_username}</td>
              <td>{entry.action}</td>
              <td>
                {entry.entity_type}: <code>{entry.entity_id}</code>
              </td>
              <td>{entry.summary}</td>
            </tr>
          ))}
          {result && result.items.length === 0 ? (
            <tr>
              <td colSpan={5} className="admin-empty-row">
                No audit entries yet.
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>

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
