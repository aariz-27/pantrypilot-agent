import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { CuisineSelect } from './CuisineSelect'

// 2026-09-13 cuisine-alignment fix: the dropdown must expose exactly
// RecipeAPI.io's documented strict-cuisine enum (plus "Any cuisine"),
// matching backend/app/recipe/provider.py's SUPPORTED_STRICT_CUISINES.
const SUPPORTED_LABELS = [
  'American',
  'Chinese',
  'French',
  'Greek',
  'Italian',
  'Japanese',
  'Mexican',
  'Portuguese',
  'Spanish',
  'Thai',
  'Turkish',
]

const UNSUPPORTED_LABELS = ['Asian', 'Indian', 'Pakistani', 'Pakistan', 'Mediterranean']

describe('CuisineSelect', () => {
  it('contains exactly the supported cuisine labels, plus "Any cuisine"', () => {
    render(<CuisineSelect value={null} onChange={vi.fn()} />)
    const options = screen.getAllByRole('option').map((o) => o.textContent)
    expect(options).toEqual(['Any cuisine', ...SUPPORTED_LABELS])
  })

  it.each(UNSUPPORTED_LABELS)('does not offer the unsupported cuisine "%s"', (label) => {
    render(<CuisineSelect value={null} onChange={vi.fn()} />)
    expect(screen.queryByRole('option', { name: label })).not.toBeInTheDocument()
  })

  it.each(SUPPORTED_LABELS)('selecting "%s" submits that exact label as the value', async (label) => {
    const onChange = vi.fn()
    render(<CuisineSelect value={null} onChange={onChange} />)
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Cuisine' }), label)
    expect(onChange).toHaveBeenCalledWith(label)
  })

  it('selecting "Any cuisine" submits null', async () => {
    const onChange = vi.fn()
    render(<CuisineSelect value="Italian" onChange={onChange} />)
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Cuisine' }), 'Any cuisine')
    expect(onChange).toHaveBeenCalledWith(null)
  })

  it('a null value displays as "Any cuisine" (optional/no-cuisine selection preserved)', () => {
    render(<CuisineSelect value={null} onChange={vi.fn()} />)
    expect(screen.getByRole('combobox', { name: 'Cuisine' })).toHaveValue('Any cuisine')
  })
})
