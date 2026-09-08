import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { TimeSelector } from './TimeSelector'

function StatefulTimeSelector({ initial = 30 }) {
  const [value, setValue] = useState(initial)
  return <TimeSelector value={value} onChange={setValue} />
}

describe('TimeSelector', () => {
  it('marks the selected preset as pressed', () => {
    render(<TimeSelector value={30} onChange={vi.fn()} />)
    expect(screen.getByRole('button', { name: '30 min' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: '15 min' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('calls onChange with the preset value when clicked', async () => {
    const onChange = vi.fn()
    render(<TimeSelector value={30} onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: '45 min' }))
    expect(onChange).toHaveBeenCalledWith(45)
  })

  it('reveals a custom numeric input when Custom is selected', async () => {
    render(<StatefulTimeSelector />)
    await userEvent.click(screen.getByRole('button', { name: 'Custom' }))
    const input = screen.getByPlaceholderText('Minutes')
    await userEvent.clear(input)
    await userEvent.type(input, '20')
    expect(input).toHaveValue(20)
  })
})
