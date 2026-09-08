import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { RecipeCard } from './RecipeCard'

function makeCard(overrides = {}) {
  return {
    recipe_id: 'recipeapi_io:1',
    provider: 'recipeapi_io',
    name: 'Chicken Fried Rice',
    image_url: null,
    source_url: null,
    cuisine: 'Asian',
    difficulty: 'easy',
    requested_servings: 4,
    provider_original_servings: 2,
    servings_scaling_applied: true,
    prep_time_minutes: 10,
    cook_time_minutes: 15,
    total_time_minutes: 25,
    pantry_coverage: 0.75,
    matched_ingredients: ['Rice', 'Chicken Breast', 'Onion'],
    missing_ingredients: [{ raw_name: 'soy sauce', canonical_id: 'soy_sauce', display_name: 'Soy Sauce', normalized_unit: 'ml', scaled_required_quantity: 100, packages_needed: 1, estimated_cost_aed: 3.5, price_complete: true, cost_confidence: 'high' }],
    unresolved_ingredients: [],
    estimated_additional_spend_aed: 3.5,
    price_complete: true,
    cost_confidence: 'high',
    instructions: 'Step 1.\nStep 2.',
    is_exact_match: true,
    deviation_reasons: [],
    ...overrides,
  }
}

describe('RecipeCard', () => {
  it('shows the pantry match percentage using the required "pantry match" wording', () => {
    render(<RecipeCard card={makeCard()} onOpen={vi.fn()} />)
    expect(screen.getByText('75% pantry match')).toBeInTheDocument()
    expect(screen.getByText(/★ 75% pantry match/)).toBeInTheDocument()
  })

  it('shows matched and missing ingredient counts', () => {
    render(<RecipeCard card={makeCard()} onOpen={vi.fn()} />)
    expect(screen.getByText('✓ 3 in your pantry')).toBeInTheDocument()
    expect(screen.getByText('✕ 1 missing')).toBeInTheDocument()
  })

  it('shows the estimated cost with the "Est." prefix, never a bare "Cost:"', () => {
    render(<RecipeCard card={makeCard()} onOpen={vi.fn()} />)
    expect(screen.getByText('Est. additional cost: AED 3.50')).toBeInTheDocument()
  })

  it('shows "unavailable" copy instead of a fabricated cost when price is incomplete', () => {
    render(<RecipeCard card={makeCard({ price_complete: false, estimated_additional_spend_aed: null })} onOpen={vi.fn()} />)
    expect(screen.getByText('Estimated additional cost unavailable')).toBeInTheDocument()
    expect(screen.queryByText(/AED 0/)).not.toBeInTheDocument()
  })

  it('renders a "No image available" placeholder when image_url is missing', () => {
    render(<RecipeCard card={makeCard({ image_url: null })} onOpen={vi.fn()} />)
    expect(screen.getByText('No image available')).toBeInTheDocument()
  })

  it('renders the real image with meaningful alt text based on the recipe name', () => {
    render(<RecipeCard card={makeCard({ image_url: 'https://example.test/img.jpg' })} onOpen={vi.fn()} />)
    expect(screen.queryByText('No image available')).not.toBeInTheDocument()
    // Grounded recipe image is meaningful content, not decorative --
    // alt text is the actual recipe name (post-review fix, 2026-09-08),
    // so it's discoverable via its accessible "img" role/name.
    expect(screen.getByRole('img', { name: 'Chicken Fried Rice' })).toHaveAttribute('src', 'https://example.test/img.jpg')
  })

  it('shows deviation reasons for a closest-alternative (non-exact) card', () => {
    render(<RecipeCard card={makeCard({ is_exact_match: false, deviation_reasons: ['12 min over your target'] })} onOpen={vi.fn()} />)
    expect(screen.getByText('12 min over your target')).toBeInTheDocument()
  })

  it('never renders a javascript: image_url as an actual img src', () => {
    const { container } = render(<RecipeCard card={makeCard({ image_url: 'javascript:alert(1)' })} onOpen={vi.fn()} />)
    expect(container.querySelector('img')).not.toBeInTheDocument()
    expect(screen.getByText('No image available')).toBeInTheDocument()
  })

  it('shows an "Alternative pick" badge when contains_active_anchor is explicitly false', () => {
    render(<RecipeCard card={makeCard({ contains_active_anchor: false })} onOpen={vi.fn()} />)
    expect(screen.getByText('Alternative pick')).toBeInTheDocument()
  })

  it('does not show the badge when contains_active_anchor is true', () => {
    render(<RecipeCard card={makeCard({ contains_active_anchor: true })} onOpen={vi.fn()} />)
    expect(screen.queryByText('Alternative pick')).not.toBeInTheDocument()
  })

  it('does not show the badge when contains_active_anchor is null (no anchor tracked)', () => {
    render(<RecipeCard card={makeCard({ contains_active_anchor: null })} onOpen={vi.fn()} />)
    expect(screen.queryByText('Alternative pick')).not.toBeInTheDocument()
  })

  it('calls onOpen with the card when clicked (whole card is tappable)', async () => {
    const onOpen = vi.fn()
    const card = makeCard()
    render(<RecipeCard card={card} onOpen={onOpen} />)
    await userEvent.click(screen.getByRole('button', { name: /Chicken Fried Rice/ }))
    expect(onOpen).toHaveBeenCalledWith(card)
  })
})
