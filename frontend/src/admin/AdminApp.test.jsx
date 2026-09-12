import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AdminApp } from './AdminApp.jsx'
import { ApiError } from '../services/api.js'
import * as adminApi from '../services/adminApi.js'

vi.mock('../services/adminApi.js', async () => {
  const actual = await vi.importActual('../services/adminApi.js')
  return {
    ...actual,
    getSession: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
    getDashboardSummary: vi.fn().mockResolvedValue({
      canonical_ingredient_count: 0,
      active_alias_count: 0,
      ingredients_with_manual_price: 0,
      ingredients_without_known_price: 0,
      mapped_product_count: 0,
      unmapped_product_count: 0,
    }),
  }
})

describe('AdminApp', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows the login screen when there is no valid session', async () => {
    adminApi.getSession.mockRejectedValue(new ApiError('Authentication required', { code: 'ADMIN_UNAUTHORIZED', status: 401 }))
    render(<AdminApp />)
    expect(await screen.findByRole('heading', { name: 'PantryPilot Admin' })).toBeInTheDocument()
    expect(screen.getByLabelText('Username')).toBeInTheDocument()
  })

  it('shows the dashboard directly when a valid session already exists (protected route allows through)', async () => {
    adminApi.getSession.mockResolvedValue({ username: 'founder', csrf_token: 'tok', expires_at: '2026-01-01T00:00:00Z' })
    render(<AdminApp />)
    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
    expect(screen.getByText('founder')).toBeInTheDocument()
  })

  it('moves from login to dashboard after a successful login', async () => {
    const user = userEvent.setup()
    adminApi.getSession.mockRejectedValue(new ApiError('Authentication required', { code: 'ADMIN_UNAUTHORIZED', status: 401 }))
    adminApi.login.mockResolvedValue({ username: 'founder', csrf_token: 'tok', expires_at: '2026-01-01T00:00:00Z' })

    render(<AdminApp />)
    await screen.findByRole('heading', { name: 'PantryPilot Admin' })

    await user.type(screen.getByLabelText('Username'), 'founder')
    await user.type(screen.getByLabelText('Password'), 'correct horse battery staple')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
  })

  it('shows a generic invalid-credentials message on login failure, never distinguishing the cause', async () => {
    const user = userEvent.setup()
    adminApi.getSession.mockRejectedValue(new ApiError('Authentication required', { code: 'ADMIN_UNAUTHORIZED', status: 401 }))
    adminApi.login.mockRejectedValue(new ApiError('Invalid username or password', { code: 'ADMIN_UNAUTHORIZED', status: 401 }))

    render(<AdminApp />)
    await screen.findByRole('heading', { name: 'PantryPilot Admin' })
    await user.type(screen.getByLabelText('Username'), 'anyone')
    await user.type(screen.getByLabelText('Password'), 'wrong')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid username or password.')
  })

  it('returns to the login screen after logout', async () => {
    const user = userEvent.setup()
    adminApi.getSession.mockResolvedValue({ username: 'founder', csrf_token: 'tok', expires_at: '2026-01-01T00:00:00Z' })
    adminApi.logout.mockResolvedValue(undefined)

    render(<AdminApp />)
    await screen.findByRole('heading', { name: 'Dashboard' })

    await user.click(screen.getByRole('button', { name: 'Log out' }))

    await waitFor(() => expect(screen.getByRole('heading', { name: 'PantryPilot Admin' })).toBeInTheDocument())
  })

  it('navigates between sidebar sections', async () => {
    const user = userEvent.setup()
    adminApi.getSession.mockResolvedValue({ username: 'founder', csrf_token: 'tok', expires_at: '2026-01-01T00:00:00Z' })

    render(<AdminApp />)
    await screen.findByRole('heading', { name: 'Dashboard' })

    await user.click(screen.getByRole('button', { name: 'Audit' }))
    expect(await screen.findByRole('heading', { name: 'Audit log' })).toBeInTheDocument()
  })
})
