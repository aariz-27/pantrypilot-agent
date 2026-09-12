import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AdminLogin } from './AdminLogin.jsx'

describe('AdminLogin responsive/basic rendering (ticket section 40)', () => {
  const originalInnerWidth = window.innerWidth

  afterEach(() => {
    window.innerWidth = originalInnerWidth
  })

  it('renders without crashing at a mobile viewport width (390px)', () => {
    window.innerWidth = 390
    render(<AdminLogin onLoginSuccess={vi.fn()} />)
    expect(screen.getByRole('heading', { name: 'PantryPilot Admin' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('renders without crashing at a desktop viewport width (1440px)', () => {
    window.innerWidth = 1440
    render(<AdminLogin onLoginSuccess={vi.fn()} />)
    expect(screen.getByRole('heading', { name: 'PantryPilot Admin' })).toBeInTheDocument()
  })

  it('requires both username and password before the browser allows submission', () => {
    render(<AdminLogin onLoginSuccess={vi.fn()} />)
    expect(screen.getByLabelText('Username')).toBeRequired()
    expect(screen.getByLabelText('Password')).toBeRequired()
  })
})
