import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { SearchForm } from './SearchForm'

vi.mock('../services/api', () => ({
  fetchIngredientSuggestions: vi.fn().mockResolvedValue([]),
}))

const BASE_STATE = {
  pantryItems: [],
  excludedItems: [],
  totalTimeMinutes: 30,
  servings: 4,
  allowHardDifficulty: false,
  cuisine: null,
  cuisineStrict: false,
  budgetAed: null,
}

function StatefulSearchForm({ initial = BASE_STATE }) {
  const [formState, setFormState] = useState(initial)
  return <SearchForm formState={formState} onChange={setFormState} onSubmit={vi.fn()} submitting={false} />
}

describe('SearchForm', () => {
  beforeEach(() => vi.clearAllMocks())

  it('disables Find meals when there is no recognized pantry ingredient', () => {
    render(<SearchForm formState={BASE_STATE} onChange={vi.fn()} onSubmit={vi.fn()} submitting={false} />)
    expect(screen.getByRole('button', { name: 'Find meals' })).toBeDisabled()
  })

  it('disables Find meals when only unresolved ingredients are present', () => {
    render(
      <SearchForm
        formState={{ ...BASE_STATE, pantryItems: [{ id: 'unresolved:kohlrabi', label: 'kohlrabi', canonical_id: null, unresolved: true }] }}
        onChange={vi.fn()}
        onSubmit={vi.fn()}
        submitting={false}
      />,
    )
    expect(screen.getByRole('button', { name: 'Find meals' })).toBeDisabled()
  })

  it('enables Find meals once a recognized ingredient and total time are set', () => {
    render(
      <SearchForm
        formState={{ ...BASE_STATE, pantryItems: [{ id: 'rice', label: 'Rice', canonical_id: 'rice', unresolved: false }] }}
        onChange={vi.fn()}
        onSubmit={vi.fn()}
        submitting={false}
      />,
    )
    expect(screen.getByRole('button', { name: 'Find meals' })).toBeEnabled()
  })

  it('disables Find meals when total time is cleared', () => {
    render(
      <SearchForm
        formState={{
          ...BASE_STATE,
          totalTimeMinutes: null,
          pantryItems: [{ id: 'rice', label: 'Rice', canonical_id: 'rice', unresolved: false }],
        }}
        onChange={vi.fn()}
        onSubmit={vi.fn()}
        submitting={false}
      />,
    )
    expect(screen.getByRole('button', { name: 'Find meals' })).toBeDisabled()
  })

  it('calls onSubmit only when the form is valid and submitted', async () => {
    const onSubmit = vi.fn()
    render(
      <SearchForm
        formState={{ ...BASE_STATE, pantryItems: [{ id: 'rice', label: 'Rice', canonical_id: 'rice', unresolved: false }] }}
        onChange={vi.fn()}
        onSubmit={onSubmit}
        submitting={false}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Find meals' }))
    expect(onSubmit).toHaveBeenCalledTimes(1)
  })

  it('defaults difficulty to Easy, Medium checked and Hard unchecked', () => {
    render(<SearchForm formState={BASE_STATE} onChange={vi.fn()} onSubmit={vi.fn()} submitting={false} />)
    expect(screen.getByRole('checkbox', { name: /Easy/ })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: /Medium/ })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Hard' })).not.toBeChecked()
  })

  it('reveals budget/exclusions/strict-cuisine only after "More options" is expanded', async () => {
    render(<SearchForm formState={BASE_STATE} onChange={vi.fn()} onSubmit={vi.fn()} submitting={false} />)
    expect(screen.queryByLabelText(/Additional grocery budget/)).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /More options/ }))
    expect(screen.getByLabelText(/Additional grocery budget/)).toBeInTheDocument()
  })

  it('shows the loading label and disables the button while submitting', () => {
    render(
      <SearchForm
        formState={{ ...BASE_STATE, pantryItems: [{ id: 'rice', label: 'Rice', canonical_id: 'rice', unresolved: false }] }}
        onChange={vi.fn()}
        onSubmit={vi.fn()}
        submitting={true}
      />,
    )
    expect(screen.getByRole('button', { name: 'Finding meals…' })).toBeDisabled()
  })

  describe('strict cuisine UX', () => {
    it('is disabled with helper text when no cuisine is selected', async () => {
      render(<StatefulSearchForm />)
      await userEvent.click(screen.getByRole('button', { name: /More options/ }))
      expect(screen.getByRole('checkbox', { name: 'Strict cuisine match' })).toBeDisabled()
      expect(screen.getByText('Choose a cuisine first')).toBeInTheDocument()
    })

    it('becomes enabled and toggleable once a cuisine is selected', async () => {
      render(<StatefulSearchForm />)
      await userEvent.click(screen.getByRole('button', { name: /More options/ }))
      await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Cuisine' }), 'Italian')

      const strictCheckbox = screen.getByRole('checkbox', { name: 'Strict cuisine match' })
      expect(strictCheckbox).toBeEnabled()
      expect(screen.queryByText('Choose a cuisine first')).not.toBeInTheDocument()

      await userEvent.click(strictCheckbox)
      expect(strictCheckbox).toBeChecked()
      await userEvent.click(strictCheckbox)
      expect(strictCheckbox).not.toBeChecked()
    })
  })
})
