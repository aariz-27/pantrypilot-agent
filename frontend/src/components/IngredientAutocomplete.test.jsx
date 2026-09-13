import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { IngredientAutocomplete } from './IngredientAutocomplete'
import * as api from '../services/api'

vi.mock('../services/api', () => ({
  fetchIngredientSuggestions: vi.fn(),
}))

function setup(props = {}) {
  const onAdd = vi.fn()
  const onRemove = vi.fn()
  render(
    <IngredientAutocomplete
      label="What ingredients do you have?"
      placeholder="Type an ingredient"
      items={[]}
      onAdd={onAdd}
      onRemove={onRemove}
      {...props}
    />,
  )
  return { onAdd, onRemove }
}

describe('IngredientAutocomplete', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches and shows suggestions as the user types', async () => {
    api.fetchIngredientSuggestions.mockResolvedValue([
      { canonical_id: 'rice', display_name: 'Rice' },
      { canonical_id: 'basmati_rice', display_name: 'Basmati Rice' },
    ])
    setup()
    await userEvent.type(screen.getByRole('combobox'), 'ric')

    await waitFor(() => expect(screen.getByText('Rice')).toBeInTheDocument())
    expect(screen.getByText('Basmati Rice')).toBeInTheDocument()
    expect(api.fetchIngredientSuggestions).toHaveBeenCalledWith('ric', expect.anything())
  })

  it('adds a resolved chip when a suggestion is selected, and clears the input', async () => {
    api.fetchIngredientSuggestions.mockResolvedValue([{ canonical_id: 'rice', display_name: 'Rice' }])
    const { onAdd } = setup()
    const input = screen.getByRole('combobox')
    await userEvent.type(input, 'ric')
    await waitFor(() => screen.getByText('Rice'))
    await userEvent.click(screen.getByText('Rice'))

    expect(onAdd).toHaveBeenCalledWith({ id: 'rice', label: 'Rice', canonical_id: 'rice', unresolved: false })
    expect(input).toHaveValue('')
  })

  it('never suggests a canonical id already added (duplicate prevention)', async () => {
    api.fetchIngredientSuggestions.mockResolvedValue([
      { canonical_id: 'rice', display_name: 'Rice' },
      { canonical_id: 'basmati_rice', display_name: 'Basmati Rice' },
    ])
    setup({ items: [{ id: 'rice', label: 'Rice', canonical_id: 'rice', unresolved: false }] })
    await userEvent.type(screen.getByRole('combobox'), 'ric')

    await waitFor(() => expect(screen.getByText('Basmati Rice')).toBeInTheDocument())
    expect(screen.queryByRole('option', { name: 'Rice' })).not.toBeInTheDocument()
  })

  it('shows "No exact match found" with a "Use ... anyway" action when nothing matches', async () => {
    api.fetchIngredientSuggestions.mockResolvedValue([])
    const { onAdd } = setup()
    await userEvent.type(screen.getByRole('combobox'), 'kohlrabi')

    await waitFor(() => expect(screen.getByText('No exact match found')).toBeInTheDocument())
    const useAnywayButton = screen.getByRole('button', { name: /Use.*kohlrabi.*anyway/ })
    await userEvent.click(useAnywayButton)

    expect(onAdd).toHaveBeenCalledWith({ id: 'unresolved:kohlrabi', label: 'kohlrabi', canonical_id: null, unresolved: true })
  })

  it('never auto-adds an unresolved term without the explicit "use anyway" action', async () => {
    api.fetchIngredientSuggestions.mockResolvedValue([])
    const { onAdd } = setup()
    await userEvent.type(screen.getByRole('combobox'), 'kohlrabi')
    await waitFor(() => expect(screen.getByText('No exact match found')).toBeInTheDocument())
    expect(onAdd).not.toHaveBeenCalled()
  })

  it('supports keyboard navigation: ArrowDown then Enter selects a suggestion', async () => {
    api.fetchIngredientSuggestions.mockResolvedValue([{ canonical_id: 'onion', display_name: 'Onion' }])
    const { onAdd } = setup()
    const input = screen.getByRole('combobox')
    await userEvent.type(input, 'onion')
    await waitFor(() => screen.getByText('Onion'))

    await userEvent.keyboard('{ArrowDown}{Enter}')
    expect(onAdd).toHaveBeenCalledWith({ id: 'onion', label: 'Onion', canonical_id: 'onion', unresolved: false })
  })

  // -- 2026-09-13 unified ingredient resolution ticket (section 31): --------
  // autocomplete is advisory, not mandatory -- Enter must commit free
  // text even when suggestions exist but none is what the user wants.

  describe('free-text entry (autocomplete is advisory, not mandatory)', () => {
    it('accepts "chicken" via Enter even though matching suggestions exist (no forced selection)', async () => {
      api.fetchIngredientSuggestions.mockResolvedValue([
        { canonical_id: 'chicken_breast', display_name: 'Chicken Breast' },
        { canonical_id: 'chicken_wings', display_name: 'Chicken Wings' },
      ])
      const { onAdd } = setup()
      const input = screen.getByRole('combobox')
      await userEvent.type(input, 'chicken')
      await waitFor(() => screen.getByText('Chicken Breast'))

      await userEvent.keyboard('{Enter}')

      expect(onAdd).toHaveBeenCalledWith({ id: 'unresolved:chicken', label: 'chicken', canonical_id: null, unresolved: true })
      expect(input).toHaveValue('')
    })

    it('accepts "mutton" via Enter with zero suggestions (already worked, still works)', async () => {
      api.fetchIngredientSuggestions.mockResolvedValue([])
      const { onAdd } = setup()
      await userEvent.type(screen.getByRole('combobox'), 'mutton')
      await waitFor(() => expect(screen.getByText('No exact match found')).toBeInTheDocument())

      await userEvent.keyboard('{Enter}')

      expect(onAdd).toHaveBeenCalledWith({ id: 'unresolved:mutton', label: 'mutton', canonical_id: null, unresolved: true })
    })

    it('accepts "lamb chops" via Enter alongside its own real suggestion, without selecting it', async () => {
      api.fetchIngredientSuggestions.mockResolvedValue([{ canonical_id: 'lamb_chops', display_name: 'Lamb Chops' }])
      const { onAdd } = setup()
      const input = screen.getByRole('combobox')
      await userEvent.type(input, 'lamb chops')
      await waitFor(() => screen.getByText('Lamb Chops'))

      await userEvent.keyboard('{Enter}')

      expect(onAdd).toHaveBeenCalledWith({
        id: 'unresolved:lamb chops', label: 'lamb chops', canonical_id: null, unresolved: true,
      })
    })

    it('a highlighted suggestion still wins over free-text commit', async () => {
      api.fetchIngredientSuggestions.mockResolvedValue([{ canonical_id: 'chicken_breast', display_name: 'Chicken Breast' }])
      const { onAdd } = setup()
      await userEvent.type(screen.getByRole('combobox'), 'chicken')
      await waitFor(() => screen.getByText('Chicken Breast'))

      await userEvent.keyboard('{ArrowDown}{Enter}')

      expect(onAdd).toHaveBeenCalledWith({ id: 'chicken_breast', label: 'Chicken Breast', canonical_id: 'chicken_breast', unresolved: false })
    })

    it('comma also commits free text', async () => {
      api.fetchIngredientSuggestions.mockResolvedValue([])
      const { onAdd } = setup()
      const input = screen.getByRole('combobox')
      await userEvent.type(input, 'basmati rice')
      await waitFor(() => expect(screen.getByText('No exact match found')).toBeInTheDocument())

      await userEvent.keyboard(',')

      expect(onAdd).toHaveBeenCalledWith({
        id: 'unresolved:basmati rice', label: 'basmati rice', canonical_id: null, unresolved: true,
      })
    })

    it('rejects an empty value (whitespace only)', async () => {
      const { onAdd } = setup()
      await userEvent.type(screen.getByRole('combobox'), '   ')
      await userEvent.keyboard('{Enter}')
      expect(onAdd).not.toHaveBeenCalled()
    })

    it('rejects an absurdly long value', async () => {
      api.fetchIngredientSuggestions.mockResolvedValue([])
      const { onAdd } = setup()
      const tooLong = 'x'.repeat(200)
      const input = screen.getByRole('combobox')
      await userEvent.type(input, tooLong)
      await waitFor(() => expect(screen.getByText('No exact match found')).toBeInTheDocument())

      await userEvent.keyboard('{Enter}')

      expect(onAdd).not.toHaveBeenCalled()
    })

    it('prevents a normalized-duplicate free-text entry', async () => {
      api.fetchIngredientSuggestions.mockResolvedValue([])
      const { onAdd } = setup({
        items: [{ id: 'unresolved:chicken', label: 'chicken', canonical_id: null, unresolved: true }],
      })
      const input = screen.getByRole('combobox')
      await userEvent.type(input, 'Chicken')
      await waitFor(() => expect(screen.getByText('No exact match found')).toBeInTheDocument())

      await userEvent.keyboard('{Enter}')

      expect(onAdd).not.toHaveBeenCalled()
      expect(input).toHaveValue('') // still clears -- a harmless repeat, not an error
    })

    it('typing a comma mid-word does not prematurely submit when there is nothing to commit yet', async () => {
      const { onAdd } = setup()
      const input = screen.getByRole('combobox')
      await userEvent.type(input, ',')
      // A bare comma with no preceding text is simply typed, not committed.
      expect(onAdd).not.toHaveBeenCalled()
    })
  })

  describe('keyboard scrolling', () => {
    // jsdom does not implement real layout/scrolling; Element.prototype
    // .scrollIntoView is stubbed per test to assert it was invoked.
    beforeEach(() => {
      Element.prototype.scrollIntoView = vi.fn()
    })

    async function setupWithManySuggestions() {
      const suggestions = Array.from({ length: 8 }, (_, i) => ({
        canonical_id: `rice_${i}`,
        display_name: `Rice Variety ${i}`,
      }))
      api.fetchIngredientSuggestions.mockResolvedValue(suggestions)
      setup()
      await userEvent.type(screen.getByRole('combobox'), 'rice')
      await waitFor(() => screen.getByText('Rice Variety 0'))
      return suggestions
    }

    it('scrolls the active option into view on ArrowDown', async () => {
      await setupWithManySuggestions()
      await userEvent.keyboard('{ArrowDown}')
      expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({ block: 'nearest' })
    })

    it('scrolls the active option into view on ArrowUp', async () => {
      await setupWithManySuggestions()
      await userEvent.keyboard('{ArrowDown}{ArrowDown}{ArrowUp}')
      expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({ block: 'nearest' })
    })

    it('does not scroll on mouse hover (preserves existing mouse behavior)', async () => {
      await setupWithManySuggestions()
      await userEvent.hover(screen.getByText('Rice Variety 3'))
      expect(Element.prototype.scrollIntoView).not.toHaveBeenCalled()
    })
  })
})
