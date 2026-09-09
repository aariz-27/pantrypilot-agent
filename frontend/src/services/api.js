// PantryPilot backend service layer -- the ONLY place that calls the
// backend HTTP API. Components must never call fetch() directly
// (docs/AGENTS.md: "no business calculations in UI components",
// docs/API_INTEGRATION_STANDARDS.md: "frontend must never call
// external providers directly" -- everything routes through this one
// PantryPilot backend boundary).

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

export class ApiError extends Error {
  constructor(message, { code, retryable, status, requestId } = {}) {
    super(message)
    this.name = 'ApiError'
    this.code = code || 'INTERNAL_ERROR'
    this.retryable = Boolean(retryable)
    this.status = status
    this.requestId = requestId
  }
}

// A 429 gets a fixed, friendly message regardless of what the backend
// body says -- rate-limit copy shouldn't depend on backend wording
// matching product tone, and the user never needs to know the word
// "rate limit" (ticket section 6: messages must be non-technical).
const RATE_LIMIT_MESSAGE = "You're searching a bit fast. Please wait a moment and try again."

async function parseErrorEnvelope(response) {
  if (response.status === 429) {
    return new ApiError(RATE_LIMIT_MESSAGE, { code: 'RATE_LIMITED', retryable: true, status: 429 })
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

// fetch() itself throws (rather than resolving with a non-ok response)
// when the backend is unreachable -- offline, DNS failure, connection
// refused, CORS rejection. Left unwrapped, that surfaces the browser's
// own technical error text (e.g. "Failed to fetch") to the user, which
// violates the "no technical/misleading messages" rule (ticket section
// 6). AbortError is passed through unchanged: it means a caller
// cancelled the request on purpose (see IngredientAutocomplete's
// superseded-request guard), not a real failure to report.
async function safeFetch(url, options) {
  try {
    return await fetch(url, options)
  } catch (err) {
    if (err.name === 'AbortError') throw err
    throw new ApiError("Can't reach PantryPilot right now. Check your connection and try again.", {
      code: 'NETWORK_ERROR',
      retryable: true,
    })
  }
}

export async function fetchIngredientSuggestions(query, { signal } = {}) {
  const params = new URLSearchParams({ q: query })
  const response = await safeFetch(`${BASE_URL}/ingredients/suggest?${params.toString()}`, { signal })
  if (!response.ok) {
    throw await parseErrorEnvelope(response)
  }
  const body = await response.json()
  return body.suggestions
}

export async function postRecommend(payload, { signal } = {}) {
  const response = await safeFetch(`${BASE_URL}/recommend`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  })
  if (!response.ok) {
    throw await parseErrorEnvelope(response)
  }
  return response.json()
}
