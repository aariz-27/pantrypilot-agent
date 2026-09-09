import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchIngredientSuggestions, postRecommend } from './api'

describe('api service error handling (Module F section 6: production UX hardening)', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('wraps a network-level fetch failure in a friendly, non-technical, retryable error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(postRecommend({})).rejects.toMatchObject({
      name: 'ApiError',
      code: 'NETWORK_ERROR',
      retryable: true,
      message: "Can't reach PantryPilot right now. Check your connection and try again.",
    })
  })

  it('passes an AbortError through unchanged instead of wrapping it', async () => {
    const abortError = new DOMException('aborted', 'AbortError')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(abortError))

    await expect(fetchIngredientSuggestions('rice')).rejects.toBe(abortError)
  })

  it('returns a fixed friendly message for a 429, ignoring whatever the backend body says', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 429,
        json: async () => ({ error: { message: 'Too Many Requests: rate limit exceeded for client 10.0.0.5' } }),
      }),
    )

    await expect(postRecommend({})).rejects.toMatchObject({
      status: 429,
      code: 'RATE_LIMITED',
      retryable: true,
      message: "You're searching a bit fast. Please wait a moment and try again.",
    })
  })

  it('surfaces the backend error envelope message for a normal 4xx', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: async () => ({
          error: { message: 'Servings must be a positive number.', code: 'VALIDATION_ERROR', retryable: false },
          request_id: 'req_1',
        }),
      }),
    )

    await expect(postRecommend({})).rejects.toMatchObject({
      status: 422,
      code: 'VALIDATION_ERROR',
      retryable: false,
      message: 'Servings must be a positive number.',
      requestId: 'req_1',
    })
  })

  it('falls back to a generic safe message -- never a raw exception -- when the error body cannot be parsed', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => {
          throw new Error('not json')
        },
      }),
    )

    await expect(postRecommend({})).rejects.toMatchObject({
      status: 500,
      message: 'Something went wrong. Please try again.',
    })
  })
})
