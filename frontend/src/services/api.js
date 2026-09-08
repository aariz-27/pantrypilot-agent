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

async function parseErrorEnvelope(response) {
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

export async function fetchIngredientSuggestions(query, { signal } = {}) {
  const params = new URLSearchParams({ q: query })
  const response = await fetch(`${BASE_URL}/ingredients/suggest?${params.toString()}`, { signal })
  if (!response.ok) {
    throw await parseErrorEnvelope(response)
  }
  const body = await response.json()
  return body.suggestions
}

export async function postRecommend(payload, { signal } = {}) {
  const response = await fetch(`${BASE_URL}/recommend`, {
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
