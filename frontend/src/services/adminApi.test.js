// Regression coverage for the admin-login-blocked-by-pre-auth-CSRF
// hotfix: adminFetch() used to require a CSRF token for every mutating
// method including POST /admin/auth/login, but no CSRF token can exist
// before a session does -- login threw ADMIN_UNAUTHORIZED client-side
// before fetch() was ever called, so no login request ever reached the
// backend in production. Fixed via an explicit `requireCsrf` option
// (default true), with login the one named exception.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clearAdminSession, createIngredient, getSession, login, logout } from './adminApi.js'

function mockFetchOnce(body, { status = 200, ok = true } = {}) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok,
    status,
    json: async () => body,
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('adminApi CSRF handling (admin-login-blocked-by-pre-auth-csrf hotfix)', () => {
  beforeEach(() => {
    clearAdminSession()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    clearAdminSession()
  })

  it('login sends its POST without requiring or attaching a CSRF token', async () => {
    const fetchMock = mockFetchOnce({ username: 'founder', csrf_token: 'tok-abc', expires_at: '2026-01-01T00:00:00Z' })

    await login('founder', 'correct horse battery staple')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toMatch(/\/admin\/auth\/login$/)
    expect(options.method).toBe('POST')
    expect(options.headers['X-Admin-CSRF-Token']).toBeUndefined()
    expect(options.credentials).toBe('include')
    expect(JSON.parse(options.body)).toEqual({ username: 'founder', password: 'correct horse battery staple' })
  })

  it('login succeeds and stores the returned csrf_token in module memory for later mutating calls', async () => {
    mockFetchOnce({ username: 'founder', csrf_token: 'tok-xyz', expires_at: '2026-01-01T00:00:00Z' })
    await login('founder', 'correct horse battery staple')

    const fetchMock = mockFetchOnce({
      canonical_id: 'onion', display_name: 'Onion', status: 'active', alias_count: 0,
    })
    await createIngredient({ canonical_id: 'onion', display_name: 'Onion', default_unit: 'g' })

    const [, options] = fetchMock.mock.calls[0]
    expect(options.headers['X-Admin-CSRF-Token']).toBe('tok-xyz')
  })

  it('an authenticated mutating call (logout) sends the stored CSRF token', async () => {
    mockFetchOnce({ username: 'founder', csrf_token: 'tok-logout', expires_at: '2026-01-01T00:00:00Z' })
    await login('founder', 'correct horse battery staple')

    const fetchMock = mockFetchOnce({ status: 'ok' })
    await logout()

    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toMatch(/\/admin\/auth\/logout$/)
    expect(options.method).toBe('POST')
    expect(options.headers['X-Admin-CSRF-Token']).toBe('tok-logout')
  })

  it('a mutating call attempted with no session/CSRF token is rejected client-side, without ever calling fetch', async () => {
    const fetchMock = mockFetchOnce({})

    await expect(createIngredient({ canonical_id: 'onion', display_name: 'Onion' })).rejects.toMatchObject({
      code: 'ADMIN_UNAUTHORIZED',
    })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('logout attempted with no session/CSRF token is also rejected client-side', async () => {
    const fetchMock = mockFetchOnce({})

    await expect(logout()).rejects.toMatchObject({ code: 'ADMIN_UNAUTHORIZED' })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('getSession (GET) is unaffected by CSRF state either way and updates the stored token', async () => {
    // No prior login/csrf token at all -- a GET must never require one.
    const fetchMock = mockFetchOnce({ username: 'founder', csrf_token: 'tok-session', expires_at: '2026-01-01T00:00:00Z' })

    const session = await getSession()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toMatch(/\/admin\/auth\/session$/)
    expect(options.method).toBe('GET')
    expect(options.headers['X-Admin-CSRF-Token']).toBeUndefined()
    expect(session.csrf_token).toBe('tok-session')

    // The freshly (re-)established token now covers a subsequent
    // mutating call -- GET /session is how a page reload recovers it.
    const mutatingFetch = mockFetchOnce({ status: 'ok' })
    await logout()
    expect(mutatingFetch.mock.calls[0][1].headers['X-Admin-CSRF-Token']).toBe('tok-session')
  })

  it('credentials: include is preserved on both login and authenticated mutating calls', async () => {
    const loginFetch = mockFetchOnce({ username: 'founder', csrf_token: 'tok-creds', expires_at: '2026-01-01T00:00:00Z' })
    await login('founder', 'pw')
    expect(loginFetch.mock.calls[0][1].credentials).toBe('include')

    const mutatingFetch = mockFetchOnce({ status: 'ok' })
    await logout()
    expect(mutatingFetch.mock.calls[0][1].credentials).toBe('include')
  })

  it('a failed login never stores a csrf token, so a subsequent mutating call still requires one', async () => {
    mockFetchOnce(
      { error: { message: 'Invalid username or password', code: 'ADMIN_UNAUTHORIZED', retryable: false } },
      { ok: false, status: 401 },
    )
    await expect(login('founder', 'wrong')).rejects.toMatchObject({ code: 'ADMIN_UNAUTHORIZED' })

    const fetchMock = mockFetchOnce({})
    await expect(logout()).rejects.toMatchObject({ code: 'ADMIN_UNAUTHORIZED' })
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
