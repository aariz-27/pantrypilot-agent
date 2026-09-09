import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ServingsStepper } from './ServingsStepper'

describe('ServingsStepper', () => {
  it('increments and decrements via onChange', async () => {
    const onChange = vi.fn()
    render(<ServingsStepper value={4} onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: 'Increase servings' }))
    expect(onChange).toHaveBeenCalledWith(5)
    await userEvent.click(screen.getByRole('button', { name: 'Decrease servings' }))
    expect(onChange).toHaveBeenCalledWith(3)
  })

  it('disables decrement at the minimum of 1', () => {
    render(<ServingsStepper value={1} onChange={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Decrease servings' })).toBeDisabled()
  })

  it('disables increment at the maximum of 20', () => {
    render(<ServingsStepper value={20} onChange={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Increase servings' })).toBeDisabled()
  })
})
