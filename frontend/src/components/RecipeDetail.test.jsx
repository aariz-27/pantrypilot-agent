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
    provider_original_servings: 4,
    servings_scaling_applied: false,
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

  describe('serving-scaling uncertainty', () => {
    it('shows "Serves N" when scaling was reliably applied', () => {
      render(<RecipeDetail card={makeCard({ requested_servings: 6, provider_original_servings: 2, servings_scaling_applied: true })} onClose={vi.fn()} />)
      expect(screen.getByText('Serves 6')).toBeInTheDocument()
      expect(screen.queryByText(/scaling unavailable/)).not.toBeInTheDocument()
    })

    it('shows "Serves N" for a known 1:1 serving count (requested equals provider original)', () => {
      render(<RecipeDetail card={makeCard({ requested_servings: 4, provider_original_servings: 4, servings_scaling_applied: false })} onClose={vi.fn()} />)
      expect(screen.getByText('Serves 4')).toBeInTheDocument()
      expect(screen.queryByText(/scaling unavailable/)).not.toBeInTheDocument()
    })

    it('shows an explicit uncertainty state when the provider original servings count is unavailable', () => {
      render(<RecipeDetail card={makeCard({ requested_servings: 4, provider_original_servings: null, servings_scaling_applied: false })} onClose={vi.fn()} />)
      expect(screen.getByText('Requested: 4 servings · quantity scaling unavailable')).toBeInTheDocument()
      expect(screen.queryByText('Serves 4')).not.toBeInTheDocument()
    })
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

  it('gives the grounded recipe image meaningful alt text based on the recipe name', () => {
    render(<RecipeDetail card={makeCard({ image_url: 'https://example.test/img.jpg', name: 'Chicken Fried Rice' })} onClose={vi.fn()} />)
    expect(screen.getByRole('img', { name: 'Chicken Fried Rice' })).toHaveAttribute('src', 'https://example.test/img.jpg')
  })

  it('traps Tab focus within the dialog (does not escape to the page behind it)', async () => {
    render(<RecipeDetail card={makeCard({ source_url: 'https://example.test/r/1' })} onClose={vi.fn()} />)
    const backButton = screen.getByRole('button', { name: 'Back to results' })
    const sourceLink = screen.getByRole('link', { name: 'View Original Recipe' })

    expect(backButton).toHaveFocus()

    // Shift+Tab from the first focusable element wraps to the last.
    await userEvent.tab({ shift: true })
    expect(sourceLink).toHaveFocus()

    // Tab from the last focusable element wraps back to the first.
    await userEvent.tab()
    expect(backButton).toHaveFocus()
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

  describe('unresolved ingredient "I have this" (Priority 3, PR #15 correction pass)', () => {
    function cardWithUnresolved() {
      return makeCard({
        unresolved_ingredients: [{ raw_name: 'Mystery Sauce', display_name: 'Mystery Sauce', identity_key: 'mystery sauce' }],
      })
    }

    it('shows an "I have this" checkbox on an uncertain row and calls onMarkHaveUnresolved with its identity_key', async () => {
      const onMarkHaveUnresolved = vi.fn()
      render(<RecipeDetail card={cardWithUnresolved()} onClose={vi.fn()} onMarkHaveUnresolved={onMarkHaveUnresolved} />)

      expect(screen.getByText('◐ Mystery Sauce')).toBeInTheDocument()
      await userEvent.click(screen.getByRole('checkbox', { name: 'I have Mystery Sauce' }))
      expect(onMarkHaveUnresolved).toHaveBeenCalledWith('mystery sauce', 'Mystery Sauce')
    })

    it('does not render a checkbox for an uncertain row when no handler is supplied', () => {
      render(<RecipeDetail card={cardWithUnresolved()} onClose={vi.fn()} />)
      expect(screen.getByText('◐ Mystery Sauce')).toBeInTheDocument()
      expect(screen.queryByRole('checkbox', { name: 'I have Mystery Sauce' })).not.toBeInTheDocument()
    })

    it('counts unresolved ingredients in the total denominator (never inflates when one is later confirmed)', () => {
      // matched(2) + missing(1) + unresolved(1) = 4 -- stable regardless
      // of which bucket an ingredient currently sits in.
      render(<RecipeDetail card={cardWithUnresolved()} onClose={vi.fn()} />)
      expect(screen.getByText('2 of 4 ingredients available')).toBeInTheDocument()
    })
  })
})
