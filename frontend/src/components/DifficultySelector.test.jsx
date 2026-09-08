import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { DifficultySelector } from './DifficultySelector'

describe('DifficultySelector', () => {
  it('defaults to Easy, Medium (Hard excluded) when allowHard is false', () => {
    render(<DifficultySelector allowHard={false} onChange={vi.fn()} />)
    expect(screen.getByRole('combobox')).toHaveValue('easy_medium')
  })

  it('calls onChange(true) when the user selects Hard', async () => {
    const onChange = vi.fn()
    render(<DifficultySelector allowHard={false} onChange={onChange} />)
    await userEvent.selectOptions(screen.getByRole('combobox'), 'Easy, Medium, Hard')
    expect(onChange).toHaveBeenCalledWith(true)
  })
})
