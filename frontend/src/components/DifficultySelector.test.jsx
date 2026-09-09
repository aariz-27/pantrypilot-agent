import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { DifficultySelector } from './DifficultySelector'

describe('DifficultySelector', () => {
  it('uses checkboxes, not a dropdown', () => {
    render(<DifficultySelector allowHard={false} onChange={vi.fn()} />)
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
    expect(screen.getAllByRole('checkbox')).toHaveLength(3)
  })

  it('defaults to Easy checked, Medium checked, Hard unchecked', () => {
    render(<DifficultySelector allowHard={false} onChange={vi.fn()} />)
    expect(screen.getByRole('checkbox', { name: /Easy/ })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: /Medium/ })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Hard' })).not.toBeChecked()
  })

  it('Easy and Medium are always checked and cannot be unchecked (no backend mechanism to exclude them)', () => {
    render(<DifficultySelector allowHard={false} onChange={vi.fn()} />)
    expect(screen.getByRole('checkbox', { name: /Easy/ })).toBeDisabled()
    expect(screen.getByRole('checkbox', { name: /Medium/ })).toBeDisabled()
  })

  it('reflects allowHard=true by checking Hard', () => {
    render(<DifficultySelector allowHard={true} onChange={vi.fn()} />)
    expect(screen.getByRole('checkbox', { name: 'Hard' })).toBeChecked()
  })

  it('calls onChange(true) when Hard is checked', async () => {
    const onChange = vi.fn()
    render(<DifficultySelector allowHard={false} onChange={onChange} />)
    await userEvent.click(screen.getByRole('checkbox', { name: 'Hard' }))
    expect(onChange).toHaveBeenCalledWith(true)
  })

  it('calls onChange(false) when Hard is unchecked', async () => {
    const onChange = vi.fn()
    render(<DifficultySelector allowHard={true} onChange={onChange} />)
    await userEvent.click(screen.getByRole('checkbox', { name: 'Hard' }))
    expect(onChange).toHaveBeenCalledWith(false)
  })

  it('the Hard checkbox is keyboard-toggleable', async () => {
    const onChange = vi.fn()
    render(<DifficultySelector allowHard={false} onChange={onChange} />)
    const hardCheckbox = screen.getByRole('checkbox', { name: 'Hard' })
    hardCheckbox.focus()
    await userEvent.keyboard(' ')
    expect(onChange).toHaveBeenCalledWith(true)
  })
})
