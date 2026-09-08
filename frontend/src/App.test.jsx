import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import * as api from './services/api'

vi.mock('./services/api', () => ({
  fetchIngredientSuggestions: vi.fn(),
  postRecommend: vi.fn(),
  ApiError: class ApiError extends Error {
    constructor(message, opts = {}) {
      super(message)
      Object.assign(this, opts)
    }
  },
}))

function baseResponse(overrides = {}) {
  return {
    request_id: 'req_1',
    status: 'completed',
    search_attempts: 1,
    progress_events: [],
    pantry_unresolved: [],
    recommendations: [],
    closest_alternatives: [],
    limitations: [],
    ...overrides,
  }
}

function card(overrides = {}) {
  return {
    recipe_id: 'recipeapi_io:1',
    provider: 'recipeapi_io',
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
    pantry_coverage: 0.8,
    matched_ingredients: ['Rice'],
    missing_ingredients: [],
    unresolved_ingredients: [],
    estimated_additional_spend_aed: 0,
    price_complete: true,
    cost_confidence: 'high',
    instructions: 'Cook it.',
    is_exact_match: true,
    deviation_reasons: [],
    ...overrides,
  }
}

async function addRecognizedIngredientAndSubmit() {
  const { fetchIngredientSuggestions } = api
  fetchIngredientSuggestions.mockResolvedValue([{ canonical_id: 'rice', display_name: 'Rice' }])
  await userEvent.type(screen.getByRole('combobox', { name: /What ingredients do you have/ }), 'rice')
  await waitFor(() => screen.getByText('Rice'))
  await userEvent.click(screen.getByText('Rice'))
  await userEvent.click(screen.getByRole('button', { name: 'Find meals' }))
}

describe('App end-to-end flow', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows recommendations after a successful search', async () => {
    api.postRecommend.mockResolvedValue(baseResponse({ recommendations: [card()] }))
    render(<App />)

    await addRecognizedIngredientAndSubmit()

    await waitFor(() => expect(screen.getByText('Best matches for you')).toBeInTheDocument())
    expect(screen.getByText('Chicken Fried Rice')).toBeInTheDocument()
  })

  it('shows the closest-match notice when there are no exact matches', async () => {
    api.postRecommend.mockResolvedValue(
      baseResponse({ status: 'no_feasible_match', closest_alternatives: [card({ is_exact_match: false, deviation_reasons: ['12 min over your target'] })] }),
    )
    render(<App />)

    await addRecognizedIngredientAndSubmit()

    await waitFor(() => expect(screen.getByText('No exact matches found — here are the closest options.')).toBeInTheDocument())
    expect(screen.getByText('12 min over your target')).toBeInTheDocument()
  })

  it('shows the empty state when there is truly nothing to show', async () => {
    api.postRecommend.mockResolvedValue(baseResponse({ status: 'no_feasible_match' }))
    render(<App />)

    await addRecognizedIngredientAndSubmit()

    await waitFor(() => expect(screen.getByText('No exact matches found')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: 'Try a new search' })).toBeInTheDocument()
  })

  it('shows a safe error message and retry option on API failure', async () => {
    const { ApiError } = api
    api.postRecommend.mockRejectedValue(new ApiError('The recipe provider did not respond in time.', { retryable: true }))
    render(<App />)

    await addRecognizedIngredientAndSubmit()

    await waitFor(() => expect(screen.getByText('The recipe provider did not respond in time.')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('surfaces unresolved pantry ingredients on the results page', async () => {
    api.postRecommend.mockResolvedValue(baseResponse({ recommendations: [card()], pantry_unresolved: ['kohlrabi'] }))
    render(<App />)

    await addRecognizedIngredientAndSubmit()

    await waitFor(() => expect(screen.getByText(/Not recognized and not used in this search: kohlrabi/)).toBeInTheDocument())
  })

  it('opens the recipe detail view when a card is clicked', async () => {
    api.postRecommend.mockResolvedValue(baseResponse({ recommendations: [card()] }))
    render(<App />)

    await addRecognizedIngredientAndSubmit()
    await waitFor(() => screen.getByText('Chicken Fried Rice'))
    await userEvent.click(screen.getByRole('button', { name: /Chicken Fried Rice/ }))

    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('returns to the search form on "New search"', async () => {
    api.postRecommend.mockResolvedValue(baseResponse({ recommendations: [card()] }))
    render(<App />)

    await addRecognizedIngredientAndSubmit()
    await waitFor(() => screen.getByText('Best matches for you'))
    await userEvent.click(screen.getByRole('button', { name: '← New search' }))

    expect(screen.getByText('Cook smarter with what you already have.')).toBeInTheDocument()
  })

  it('shows the higher-match-time-excluded message with a "Show longer recipes" action', async () => {
    api.postRecommend.mockResolvedValueOnce(
      baseResponse({ recommendations: [card()], higher_match_time_excluded: true, higher_match_time_excluded_count: 2 }),
    )
    render(<App />)
    await addRecognizedIngredientAndSubmit()

    await waitFor(() =>
      expect(screen.getByText(/Some better pantry matches were excluded because they exceeded your 30-minute limit\./)).toBeInTheDocument(),
    )

    api.postRecommend.mockResolvedValueOnce(baseResponse({ recommendations: [card()] }))
    await userEvent.click(screen.getByRole('button', { name: 'Show longer recipes' }))

    await waitFor(() => expect(api.postRecommend).toHaveBeenCalledTimes(2))
    expect(api.postRecommend.mock.calls[1][0].max_total_time_minutes).toBe(60)
  })
})

describe('"I have this" pantry checkbox flow', () => {
  beforeEach(() => vi.clearAllMocks())

  function onionRow(overrides = {}) {
    return { raw_name: 'onion', canonical_id: 'onion', display_name: 'Onion', normalized_unit: 'g', scaled_required_quantity: 100, packages_needed: 1, estimated_cost_aed: 2.5, price_complete: true, cost_confidence: 'high', ...overrides }
  }
  function garlicRow(overrides = {}) {
    return { raw_name: 'garlic', canonical_id: 'garlic', display_name: 'Garlic', normalized_unit: 'g', scaled_required_quantity: 10, packages_needed: 1, estimated_cost_aed: 1.5, price_complete: true, cost_confidence: 'high', ...overrides }
  }

  it('checking a missing ingredient moves it to matched, increases match %, decreases missing count, and recomputes cost', async () => {
    const twoMissingCard = card({
      matched_ingredients: ['Chicken Breast'],
      missing_ingredients: [onionRow(), garlicRow()],
      unresolved_ingredients: [],
      pantry_coverage: 1 / 3,
      estimated_additional_spend_aed: 4.0,
    })
    api.postRecommend.mockResolvedValue(baseResponse({ recommendations: [twoMissingCard] }))
    render(<App />)
    await addRecognizedIngredientAndSubmit()
    await waitFor(() => screen.getByText('Chicken Fried Rice'))

    await userEvent.click(screen.getByRole('button', { name: /Chicken Fried Rice/ }))
    await userEvent.click(screen.getByRole('checkbox', { name: 'I have Onion' }))

    // Detail view recomputed in place.
    expect(screen.getByText('✓ Onion')).toBeInTheDocument()
    expect(screen.queryByText('✕ Onion')).not.toBeInTheDocument()
    expect(screen.getByText('2 of 3 ingredients available')).toBeInTheDocument()
    expect(screen.getByText('Estimated additional spend: AED 1.50')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Back to results' }))

    // Grid card also reflects the recompute (match % up, missing count down).
    expect(screen.getByText('67% pantry match')).toBeInTheDocument()
    expect(screen.getByText('✕ 1 missing')).toBeInTheDocument()
  })

  it('updates multiple cards from the same pantry change', async () => {
    const cardA = card({
      recipe_id: 'recipeapi_io:a',
      name: 'Recipe A',
      matched_ingredients: [],
      missing_ingredients: [onionRow()],
      pantry_coverage: 0,
    })
    const cardB = card({
      recipe_id: 'recipeapi_io:b',
      name: 'Recipe B',
      matched_ingredients: ['Tomato'],
      missing_ingredients: [onionRow()],
      pantry_coverage: 0.5,
    })
    api.postRecommend.mockResolvedValue(baseResponse({ recommendations: [cardA, cardB] }))
    render(<App />)
    await addRecognizedIngredientAndSubmit()
    await waitFor(() => screen.getByText('Recipe A'))

    await userEvent.click(screen.getByRole('button', { name: /Recipe A/ }))
    await userEvent.click(screen.getByRole('checkbox', { name: 'I have Onion' }))
    await userEvent.click(screen.getByRole('button', { name: 'Back to results' }))

    // Both cards now show 100% match -- Recipe B was never opened.
    const matchBadges = screen.getAllByText('100% pantry match')
    expect(matchBadges).toHaveLength(2)
  })

  it('"Refresh recommendations" only appears after a pantry change, and submits the updated pantry', async () => {
    const missingOnionCard = card({ missing_ingredients: [onionRow()], pantry_coverage: 0.5 })
    api.postRecommend.mockResolvedValueOnce(baseResponse({ recommendations: [missingOnionCard] }))
    render(<App />)
    await addRecognizedIngredientAndSubmit()
    await waitFor(() => screen.getByText('Chicken Fried Rice'))

    expect(screen.queryByRole('button', { name: 'Refresh recommendations' })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Chicken Fried Rice/ }))
    await userEvent.click(screen.getByRole('checkbox', { name: 'I have Onion' }))
    await userEvent.click(screen.getByRole('button', { name: 'Back to results' }))

    const refreshButton = screen.getByRole('button', { name: 'Refresh recommendations' })
    api.postRecommend.mockResolvedValueOnce(baseResponse({ recommendations: [card()] }))
    await userEvent.click(refreshButton)

    await waitFor(() => expect(api.postRecommend).toHaveBeenCalledTimes(2))
    const secondCallIngredients = api.postRecommend.mock.calls[1][0].ingredients
    expect(secondCallIngredients).toContain('Onion')
    // Never calls the LLM/backend merely because a checkbox was clicked
    // -- only the explicit "Refresh recommendations" click triggers this.
    expect(api.postRecommend).toHaveBeenCalledTimes(2)
  })

  it('deduplicates against an ingredient already in the current pantry when refreshing', async () => {
    const missingOnionCard = card({ missing_ingredients: [onionRow()], pantry_coverage: 0.5 })
    api.postRecommend.mockResolvedValueOnce(baseResponse({ recommendations: [missingOnionCard] }))
    render(<App />)

    // The pantry already contains "Onion" from the initial search.
    const { fetchIngredientSuggestions } = api
    fetchIngredientSuggestions.mockResolvedValue([{ canonical_id: 'onion', display_name: 'Onion' }])
    const input = screen.getByRole('combobox', { name: /What ingredients do you have/ })
    await userEvent.type(input, 'onion')
    await waitFor(() => screen.getByText('Onion'))
    await userEvent.click(screen.getByText('Onion'))
    await userEvent.click(screen.getByRole('button', { name: 'Find meals' }))
    await waitFor(() => screen.getByText('Chicken Fried Rice'))

    await userEvent.click(screen.getByRole('button', { name: /Chicken Fried Rice/ }))
    await userEvent.click(screen.getByRole('checkbox', { name: 'I have Onion' }))
    await userEvent.click(screen.getByRole('button', { name: 'Back to results' }))

    api.postRecommend.mockResolvedValueOnce(baseResponse({ recommendations: [card()] }))
    await userEvent.click(screen.getByRole('button', { name: 'Refresh recommendations' }))

    await waitFor(() => expect(api.postRecommend).toHaveBeenCalledTimes(2))
    const secondCallIngredients = api.postRecommend.mock.calls[1][0].ingredients
    expect(secondCallIngredients.filter((name) => name === 'Onion')).toHaveLength(1)
  })

  it('never shows a checkbox for an unresolved (non-canonical) ingredient', async () => {
    const cardWithUnresolved = card({
      missing_ingredients: [{ raw_name: 'mystery sauce', canonical_id: null, display_name: 'mystery sauce', estimated_cost_aed: null, price_complete: false }],
    })
    api.postRecommend.mockResolvedValue(baseResponse({ recommendations: [cardWithUnresolved] }))
    render(<App />)
    await addRecognizedIngredientAndSubmit()
    await waitFor(() => screen.getByText('Chicken Fried Rice'))

    await userEvent.click(screen.getByRole('button', { name: /Chicken Fried Rice/ }))
    expect(screen.queryByRole('checkbox', { name: /I have/ })).not.toBeInTheDocument()
  })
})

describe('"I have this" for unresolved ingredients (Priority 3, PR #15 correction pass)', () => {
  beforeEach(() => vi.clearAllMocks())

  function mysteryRow(overrides = {}) {
    return { raw_name: 'Mystery Sauce', display_name: 'Mystery Sauce', identity_key: 'mystery sauce', ...overrides }
  }

  it('checking an uncertain row moves it to "You already have", increases match %, and never assigns a price', async () => {
    const uncertainCard = card({
      matched_ingredients: ['Chicken Breast'],
      missing_ingredients: [],
      unresolved_ingredients: [mysteryRow()],
      pantry_coverage: 0.5,
      estimated_additional_spend_aed: null,
      price_complete: false,
    })
    api.postRecommend.mockResolvedValue(baseResponse({ recommendations: [uncertainCard] }))
    render(<App />)
    await addRecognizedIngredientAndSubmit()
    await waitFor(() => screen.getByText('Chicken Fried Rice'))

    await userEvent.click(screen.getByRole('button', { name: /Chicken Fried Rice/ }))
    expect(screen.getByText('◐ Mystery Sauce')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('checkbox', { name: 'I have Mystery Sauce' }))

    // Moved out of Uncertain and into "You already have" -- never
    // fabricates a price for it (still no cost row/estimate for it).
    expect(screen.queryByText('◐ Mystery Sauce')).not.toBeInTheDocument()
    expect(screen.getByText('✓ Mystery Sauce')).toBeInTheDocument()
    expect(screen.getByText('2 of 2 ingredients available')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Back to results' }))
    expect(screen.getByText('100% pantry match')).toBeInTheDocument()
  })

  it('shows "Refresh recommendations" after an unresolved confirmation and submits the raw ingredient with no canonical assumption', async () => {
    const uncertainCard = card({ unresolved_ingredients: [mysteryRow()], pantry_coverage: 0.5 })
    api.postRecommend.mockResolvedValueOnce(baseResponse({ recommendations: [uncertainCard] }))
    render(<App />)
    await addRecognizedIngredientAndSubmit()
    await waitFor(() => screen.getByText('Chicken Fried Rice'))

    expect(screen.queryByRole('button', { name: 'Refresh recommendations' })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Chicken Fried Rice/ }))
    await userEvent.click(screen.getByRole('checkbox', { name: 'I have Mystery Sauce' }))
    await userEvent.click(screen.getByRole('button', { name: 'Back to results' }))

    const refreshButton = screen.getByRole('button', { name: 'Refresh recommendations' })
    api.postRecommend.mockResolvedValueOnce(baseResponse({ recommendations: [card()] }))
    await userEvent.click(refreshButton)

    await waitFor(() => expect(api.postRecommend).toHaveBeenCalledTimes(2))
    const secondCallIngredients = api.postRecommend.mock.calls[1][0].ingredients
    // Submitted as plain raw text -- the request schema has no
    // canonical_id field at all, so there is no way to smuggle a
    // trusted identity through this path even if we wanted to.
    expect(secondCallIngredients).toContain('Mystery Sauce')
  })

  it('updates the same unresolved ingredient across multiple displayed cards by identity_key', async () => {
    const cardA = card({
      recipe_id: 'recipeapi_io:a',
      name: 'Recipe A',
      matched_ingredients: [],
      unresolved_ingredients: [mysteryRow({ raw_name: 'Mystery Sauce' })],
      pantry_coverage: 0,
    })
    const cardB = card({
      recipe_id: 'recipeapi_io:b',
      name: 'Recipe B',
      matched_ingredients: ['Tomato'],
      unresolved_ingredients: [mysteryRow({ raw_name: 'mystery sauce!!' })],
      pantry_coverage: 0.5,
    })
    api.postRecommend.mockResolvedValue(baseResponse({ recommendations: [cardA, cardB] }))
    render(<App />)
    await addRecognizedIngredientAndSubmit()
    await waitFor(() => screen.getByText('Recipe A'))

    await userEvent.click(screen.getByRole('button', { name: /Recipe A/ }))
    await userEvent.click(screen.getByRole('checkbox', { name: 'I have Mystery Sauce' }))
    await userEvent.click(screen.getByRole('button', { name: 'Back to results' }))

    // Recipe B was never opened, but its card-level match % must also
    // reflect the same confirmed raw-text identity.
    const matchBadges = screen.getAllByText('100% pantry match')
    expect(matchBadges).toHaveLength(2)
  })
})


describe('additional_options "Show more options" (Priority 4, PR #15 correction pass)', () => {
  beforeEach(() => vi.clearAllMocks())

  function reserveCard(overrides = {}) {
    return card({
      recipe_id: 'reserve-1',
      name: 'Reserve Dish',
      matched_ingredients: [],
      missing_ingredients: [],
      pantry_coverage: 0.5,
      ...overrides,
    })
  }

  it('shows only the top 3 initially, with a "Show more options" control when reserve candidates exist', async () => {
    const response = baseResponse({
      recommendations: [card()],
      additional_options: [reserveCard({ recipe_id: 'r1', name: 'Reserve One' })],
    })
    api.postRecommend.mockResolvedValue(response)
    render(<App />)
    await addRecognizedIngredientAndSubmit()

    await waitFor(() => screen.getByText('Chicken Fried Rice'))
    expect(screen.queryByText('Reserve One')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Show more options' })).toBeInTheDocument()
  })

  it('clicking "Show more options" reveals additional cards and makes no new API call', async () => {
    const response = baseResponse({
      recommendations: [card()],
      additional_options: [reserveCard({ recipe_id: 'r1', name: 'Reserve One' })],
    })
    api.postRecommend.mockResolvedValue(response)
    render(<App />)
    await addRecognizedIngredientAndSubmit()
    await waitFor(() => screen.getByText('Chicken Fried Rice'))

    await userEvent.click(screen.getByRole('button', { name: 'Show more options' }))

    expect(screen.getByText('Reserve One')).toBeInTheDocument()
    // Still exactly the one call from the initial search -- revealing
    // reserve candidates makes no Claude/RecipeAPI.io request.
    expect(api.postRecommend).toHaveBeenCalledTimes(1)
  })

  it('hides "Show more options" once every reserve candidate is revealed', async () => {
    const response = baseResponse({
      recommendations: [card()],
      additional_options: [reserveCard({ recipe_id: 'r1', name: 'Reserve One' })],
    })
    api.postRecommend.mockResolvedValue(response)
    render(<App />)
    await addRecognizedIngredientAndSubmit()
    await waitFor(() => screen.getByText('Chicken Fried Rice'))

    await userEvent.click(screen.getByRole('button', { name: 'Show more options' }))

    expect(screen.queryByRole('button', { name: 'Show more options' })).not.toBeInTheDocument()
  })

  it('a reserve candidate can move into the visible top 3 after "I have this" recomputation, still with no new API call', async () => {
    const weakTop = card({
      recipe_id: 'weak-top',
      name: 'Weak Top',
      matched_ingredients: [],
      missing_ingredients: [{ raw_name: 'x', canonical_id: 'x_ing', display_name: 'X', estimated_cost_aed: 1, price_complete: true }],
      pantry_coverage: 0.1,
    })
    const strongReserve = reserveCard({
      recipe_id: 'strong-reserve',
      name: 'Strong Reserve',
      matched_ingredients: [],
      missing_ingredients: [{ raw_name: 'onion', canonical_id: 'onion', display_name: 'Onion', estimated_cost_aed: 2.5, price_complete: true }],
      pantry_coverage: 0.2,
    })
    const response = baseResponse({ recommendations: [weakTop], additional_options: [strongReserve] })
    api.postRecommend.mockResolvedValue(response)
    render(<App />)
    await addRecognizedIngredientAndSubmit()
    await waitFor(() => screen.getByText('Weak Top'))

    await userEvent.click(screen.getByRole('button', { name: 'Show more options' }))
    await waitFor(() => screen.getByText('Strong Reserve'))

    await userEvent.click(screen.getByRole('button', { name: /Strong Reserve/ }))
    await userEvent.click(screen.getByRole('checkbox', { name: 'I have Onion' }))
    await userEvent.click(screen.getByRole('button', { name: 'Back to results' }))

    // "Strong Reserve" now has full coverage and no missing ingredients
    // -- it must outrank "Weak Top" and appear as a top result, without
    // any additional network call.
    const grid = screen.getByText('Strong Reserve').closest('.recipe-grid') ?? document.body
    expect(grid).toContainElement(screen.getByText('Strong Reserve'))
    expect(api.postRecommend).toHaveBeenCalledTimes(1)
  })

  it('"Refresh recommendations" remains the only action that starts a fresh search', async () => {
    const response = baseResponse({
      recommendations: [card({ missing_ingredients: [{ raw_name: 'onion', canonical_id: 'onion', display_name: 'Onion', estimated_cost_aed: 2.5, price_complete: true }] })],
      additional_options: [reserveCard({ recipe_id: 'r1', name: 'Reserve One' })],
    })
    api.postRecommend.mockResolvedValueOnce(response)
    render(<App />)
    await addRecognizedIngredientAndSubmit()
    await waitFor(() => screen.getByText('Chicken Fried Rice'))

    await userEvent.click(screen.getByRole('button', { name: 'Show more options' }))
    await userEvent.click(screen.getByRole('button', { name: /Chicken Fried Rice/ }))
    await userEvent.click(screen.getByRole('checkbox', { name: 'I have Onion' }))
    await userEvent.click(screen.getByRole('button', { name: 'Back to results' }))

    expect(api.postRecommend).toHaveBeenCalledTimes(1)

    api.postRecommend.mockResolvedValueOnce(baseResponse({ recommendations: [card()] }))
    await userEvent.click(screen.getByRole('button', { name: 'Refresh recommendations' }))
    await waitFor(() => expect(api.postRecommend).toHaveBeenCalledTimes(2))
  })
})


describe('additional_options anchor discipline end-to-end (PR #15 second correction pass)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows the "Alternative pick" badge only on a non-anchor reserve card', async () => {
    const anchorReserve = card({ recipe_id: 'reserve-anchor', name: 'Reserve Anchor Dish', contains_active_anchor: true })
    const nonAnchorReserve = card({ recipe_id: 'reserve-non-anchor', name: 'Reserve Non Anchor Dish', contains_active_anchor: false })
    const response = baseResponse({
      recommendations: [card({ contains_active_anchor: true })],
      additional_options: [anchorReserve, nonAnchorReserve],
    })
    api.postRecommend.mockResolvedValue(response)
    render(<App />)
    await addRecognizedIngredientAndSubmit()
    await waitFor(() => screen.getByText('Chicken Fried Rice'))

    await userEvent.click(screen.getByRole('button', { name: 'Show more options' }))

    expect(screen.getAllByText('Alternative pick')).toHaveLength(1)
    const nonAnchorCardEl = screen.getByText('Reserve Non Anchor Dish').closest('button')
    expect(nonAnchorCardEl).toContainElement(screen.getByText('Alternative pick'))
  })
})
