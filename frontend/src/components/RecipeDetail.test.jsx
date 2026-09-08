import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { RecipeDetail } from './RecipeDetail'

function makeCard(overrides = {}) {
  return {
    recipe_id: 'recipeapi_io:1',
    name: 'Chicken Fried Rice',
    image_url: null,
    source_url: null,
    cuisine: 'Asian',
    difficulty: 'easy',
    requested_servings: 4,
    prep_time_minutes: 10,
    cook_time_minutes: 15,
    total_time_minutes: 25,
    pantry_coverage: 0.75,
    matched_ingredients: ['Rice', 'Chicken Breast'],
    missing_ingredients: [{ raw_name: 'soy sauce', canonical_id: 'soy_sauce', display_name: 'Soy Sauce', estimated_cost_aed: 3.5, price_complete: true }],
    unresolved_ingredients: [],
    estimated_additional_spend_aed: 3.5,
    price_complete: true,
    instructions: 'Cook everything together.',
    ...overrides,
  }
}

describe('RecipeDetail', () => {
  it('renders matched ingredients with a check and missing ingredients with cost', () => {
    render(<RecipeDetail card={makeCard()} onClose={vi.fn()} />)
    expect(screen.getByText('✓ Rice')).toBeInTheDocument()
    expect(screen.getByText('✓ Chicken Breast')).toBeInTheDocument()
    expect(screen.getByText('✕ Soy Sauce')).toBeInTheDocument()
    expect(screen.getByText('Est. AED 3.50')).toBeInTheDocument()
  })

  it('shows the pantry coverage count, not an AI-confidence framing', () => {
    render(<RecipeDetail card={makeCard()} onClose={vi.fn()} />)
    expect(screen.getByText('2 of 3 ingredients available')).toBeInTheDocument()
  })

  it('shows "View Original Recipe" only when source_url is present', () => {
    const { rerender } = render(<RecipeDetail card={makeCard({ source_url: null })} onClose={vi.fn()} />)
    expect(screen.queryByRole('link', { name: 'View Original Recipe' })).not.toBeInTheDocument()

    rerender(<RecipeDetail card={makeCard({ source_url: 'https://example.test/r/1' })} onClose={vi.fn()} />)
    expect(screen.getByRole('link', { name: 'View Original Recipe' })).toHaveAttribute('href', 'https://example.test/r/1')
  })

  it('never renders a javascript: source_url as a clickable link', () => {
    render(<RecipeDetail card={makeCard({ source_url: 'javascript:alert(1)' })} onClose={vi.fn()} />)
    expect(screen.queryByRole('link', { name: 'View Original Recipe' })).not.toBeInTheDocument()
  })

  it('calls onClose when Escape is pressed', async () => {
    const onClose = vi.fn()
    render(<RecipeDetail card={makeCard()} onClose={onClose} />)
    await userEvent.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalled()
  })

  it('calls onClose when the back button is activated', async () => {
    const onClose = vi.fn()
    render(<RecipeDetail card={makeCard()} onClose={onClose} />)
    await userEvent.click(screen.getByRole('button', { name: 'Back to results' }))
    expect(onClose).toHaveBeenCalled()
  })

  it('moves focus to the close control on open (focus management)', () => {
    render(<RecipeDetail card={makeCard()} onClose={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Back to results' })).toHaveFocus()
  })

  it('exposes an accessible dialog role', () => {
    render(<RecipeDetail card={makeCard()} onClose={vi.fn()} />)
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('renders multi-line instructions as a numbered steps list', () => {
    render(<RecipeDetail card={makeCard({ instructions: 'Chop onions.\nFry chicken.\nAdd rice.' })} onClose={vi.fn()} />)
    const lists = screen.getAllByRole('list')
    expect(lists.some((el) => el.tagName === 'OL')).toBe(true)
    expect(screen.getByText('Chop onions.')).toBeInTheDocument()
  })
})
