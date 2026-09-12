// Admin dashboard service layer -- the ONLY place the admin UI calls
// the backend /api/admin/* namespace, mirroring the existing
// api.js convention (docs/API_INTEGRATION_STANDARDS.md: components
// never call fetch() directly).
//
// The CSRF token lives ONLY in this module-level variable, never in
// localStorage/sessionStorage and never in a readable cookie -- it is
// handed to the frontend exclusively in the JSON body of
// /admin/auth/login and /admin/auth/session responses (backend ticket
// section 7). A full page reload loses it; getSession() below
// re-fetches it using the still-valid HttpOnly session cookie the
// browser sends automatically.

import { ApiError } from './api.js'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

let csrfToken = null

export function clearAdminSession() {
  csrfToken = null
}

async function parseErrorEnvelope(response) {
  if (response.status === 429) {
    return new ApiError('Too many attempts. Please wait a moment and try again.', {
      code: 'RATE_LIMITED',
      retryable: true,
      status: 429,
    })
  }
  try {
    const body = await response.json()
    if (body && body.error) {
      return new ApiError(body.error.message || 'Something went wrong.', {
        code: body.error.code,
        retryable: body.error.retryable,
        status: response.status,
        requestId: body.request_id,
      })
    }
  } catch {
    // fall through to generic error below
  }
  return new ApiError('Something went wrong. Please try again.', { status: response.status })
}

async function safeFetch(url, options) {
  try {
    return await fetch(url, options)
  } catch {
    throw new ApiError("Can't reach the admin API right now. Check your connection and try again.", {
      code: 'NETWORK_ERROR',
      retryable: true,
    })
  }
}

const MUTATING_METHODS = new Set(['POST', 'PATCH', 'DELETE', 'PUT'])

async function adminFetch(path, { method = 'GET', body, requireCsrf = true } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  // requireCsrf defaults to true for every mutating call -- login is
  // the one narrow, explicit exception (there is no session yet to
  // hold a CSRF token before authentication succeeds), never a broad
  // "unauthenticated POSTs skip CSRF" rule. The backend's own
  // require_csrf dependency independently enforces this regardless of
  // what the frontend sends, so this can never weaken real CSRF
  // protection -- it only fixes which requests the frontend attempts.
  if (MUTATING_METHODS.has(method) && requireCsrf) {
    if (!csrfToken) {
      throw new ApiError('Your admin session expired. Please sign in again.', { code: 'ADMIN_UNAUTHORIZED', status: 401 })
    }
    headers['X-Admin-CSRF-Token'] = csrfToken
  }

  const response = await safeFetch(`${BASE_URL}${path}`, {
    method,
    headers,
    credentials: 'include',
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!response.ok) {
    throw await parseErrorEnvelope(response)
  }
  if (response.status === 204) return null
  return response.json()
}

// -- auth --------------------------------------------------------------

export async function login(username, password) {
  // No session/CSRF token can exist before login succeeds -- this is
  // the one explicit, named exception to the default CSRF requirement
  // (see adminFetch). The backend's own login route has no CSRF
  // dependency either (app.admin.deps.require_csrf only applies to
  // routes that already require an authenticated session), so this
  // doesn't weaken anything the backend enforces.
  const session = await adminFetch('/admin/auth/login', {
    method: 'POST',
    body: { username, password },
    requireCsrf: false,
  })
  csrfToken = session.csrf_token
  return session
}

export async function logout() {
  try {
    await adminFetch('/admin/auth/logout', { method: 'POST', body: {} })
  } finally {
    clearAdminSession()
  }
}

export async function getSession() {
  const session = await adminFetch('/admin/auth/session')
  csrfToken = session.csrf_token
  return session
}

// -- ingredients ---------------------------------------------------------

export function listIngredients({ q, status, page = 1, pageSize = 25 } = {}) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (q) params.set('q', q)
  if (status) params.set('status', status)
  return adminFetch(`/admin/ingredients?${params.toString()}`)
}

export function getIngredient(canonicalId) {
  return adminFetch(`/admin/ingredients/${encodeURIComponent(canonicalId)}`)
}

export function createIngredient(payload) {
  return adminFetch('/admin/ingredients', { method: 'POST', body: payload })
}

export function updateIngredient(canonicalId, patch) {
  return adminFetch(`/admin/ingredients/${encodeURIComponent(canonicalId)}`, { method: 'PATCH', body: patch })
}

// -- aliases ---------------------------------------------------------------

export function listAliases(canonicalId, { includeInactive = false } = {}) {
  const params = new URLSearchParams({ include_inactive: String(includeInactive) })
  return adminFetch(`/admin/ingredients/${encodeURIComponent(canonicalId)}/aliases?${params.toString()}`)
}

export function createAlias(canonicalId, alias, source = 'manual') {
  return adminFetch(`/admin/ingredients/${encodeURIComponent(canonicalId)}/aliases`, {
    method: 'POST',
    body: { alias, source },
  })
}

export function reassignAlias(alias, newCanonicalId) {
  return adminFetch(`/admin/aliases/${encodeURIComponent(alias)}`, {
    method: 'PATCH',
    body: { new_canonical_id: newCanonicalId, confirm_reassignment: true },
  })
}

export function deactivateAlias(alias) {
  return adminFetch(`/admin/aliases/${encodeURIComponent(alias)}`, { method: 'DELETE' })
}

// -- prices ------------------------------------------------------------

export function getIngredientPrices(canonicalId) {
  return adminFetch(`/admin/ingredients/${encodeURIComponent(canonicalId)}/prices`)
}

export function createManualPrice(canonicalId, payload) {
  return adminFetch(`/admin/ingredients/${encodeURIComponent(canonicalId)}/prices`, { method: 'POST', body: payload })
}

export function updateManualPrice(canonicalId, normalizedUnit, patch) {
  return adminFetch(`/admin/prices/${encodeURIComponent(canonicalId)}/${encodeURIComponent(normalizedUnit)}`, {
    method: 'PATCH',
    body: patch,
  })
}

export function deactivateManualPrice(canonicalId, normalizedUnit) {
  return adminFetch(`/admin/prices/${encodeURIComponent(canonicalId)}/${encodeURIComponent(normalizedUnit)}`, {
    method: 'DELETE',
  })
}

// -- dashboard / audit / grocery data mapping -----------------------------

export function getDashboardSummary() {
  return adminFetch('/admin/dashboard/summary')
}

export function listAuditEntries({ entityType, page = 1, pageSize = 25 } = {}) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (entityType) params.set('entity_type', entityType)
  return adminFetch(`/admin/audit?${params.toString()}`)
}

export function listGroceryProducts({ status, q, page = 1, pageSize = 25 } = {}) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (status) params.set('status', status)
  if (q) params.set('q', q)
  return adminFetch(`/admin/grocery/products?${params.toString()}`)
}
