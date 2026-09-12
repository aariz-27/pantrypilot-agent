// Simple modal confirmation (ticket section 29) -- used for every
// destructive/deactivating action (alias removal, price removal) so a
// destructive click is never one accidental tap away from a SAVE
// button (ticket section 18).

export function ConfirmDialog({ title, message, confirmLabel, onConfirm, onCancel }) {
  return (
    <div className="admin-modal-overlay" onMouseDown={(e) => e.target === e.currentTarget && onCancel()}>
      <div className="card admin-modal" role="alertdialog" aria-modal="true" aria-labelledby="admin-confirm-title">
        <h2 id="admin-confirm-title" className="admin-section__title">
          {title}
        </h2>
        <p>{message}</p>
        <div className="admin-modal__actions">
          <button type="button" className="btn btn-secondary" onClick={onCancel}>
            Cancel
          </button>
          <button type="button" className="btn admin-destructive-btn" onClick={onConfirm}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
