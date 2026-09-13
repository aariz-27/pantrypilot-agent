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

    // getByText only concatenates an element's DIRECT text-node
    // children, not nested-element text -- the headline's "already
    // have" is wrapped in its own <span> for gold emphasis, so the
    // accessible-name-based role query (which does compute across
    // nested elements) is used here instead.
    expect(screen.getByRole('heading', { name: 'Cook smarter with what you already have.' })).toBeInTheDocument()
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


describe('additional_options "Show more options" (initial reveal 3 -> 6, frontend polish patch)', () => {
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

  // With a single top recommendation, the initial reveal pulls 5
  // additional_options (1 + 5 = 6 shown total) -- these fillers occupy
  // exactly that initial slice so a 6th/"real" reserve card placed
  // after them stays hidden until "Show more options" is clicked.
  function fillerReserves(count) {
    return Array.from({ length: count }, (_, i) => reserveCard({ recipe_id: `filler-${i}`, name: `Filler Reserve ${i + 1}` }))
  }

  it('shows up to 6 initially (recommendations + already-evaluated reserve candidates), with "Show more options" when more exist beyond that', async () => {
    const response = baseResponse({
      recommendations: [card()],
      additional_options: [...fillerReserves(5), reserveCard({ recipe_id: 'r1', name: 'Reserve One' })],
    })
    api.postRecommend.mockResolvedValue(response)
    render(<App />)
    await addRecognizedIngredientAndSubmit()

    await waitFor(() => screen.getByText('Chicken Fried Rice'))
    // 1 recommendation + the first 5 reserve candidates = 6 shown already.
    expect(screen.getByText('Filler Reserve 5')).toBeInTheDocument()
    expect(screen.queryByText('Reserve One')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Show more options' })).toBeInTheDocument()
  })

  it('shows exactly what is available when fewer than 6 feasible recipes exist (never padded)', async () => {
    const response = baseResponse({
      recommendations: [card()],
      additional_options: [reserveCard({ recipe_id: 'r1', name: 'Reserve One' })],
    })
    api.postRecommend.mockResolvedValue(response)
    render(<App />)
    await addRecognizedIngredientAndSubmit()

    await waitFor(() => screen.getByText('Chicken Fried Rice'))
    // Only 2 candidates exist in total (1 recommendation + 1 reserve) --
    // both show immediately, and there is nothing left to reveal.
    expect(screen.getByText('Reserve One')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Show more options' })).not.toBeInTheDocument()
  })

  it('clicking "Show more options" reveals further cards and makes no new API call', async () => {
    const response = baseResponse({
      recommendations: [card()],
      additional_options: [...fillerReserves(5), reserveCard({ recipe_id: 'r1', name: 'Reserve One' })],
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
      additional_options: [...fillerReserves(5), reserveCard({ recipe_id: 'r1', name: 'Reserve One' })],
    })
    api.postRecommend.mockResolvedValue(response)
    render(<App />)
    await addRecognizedIngredientAndSubmit()
    await waitFor(() => screen.getByText('Chicken Fried Rice'))

    await userEvent.click(screen.getByRole('button', { name: 'Show more options' }))

    expect(screen.queryByRole('button', { name: 'Show more options' })).not.toBeInTheDocument()
  })

  it('a reserve candidate can move into the visible recommendations after "I have this" recomputation, still with no new API call', async () => {
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
    const response = baseResponse({
      recommendations: [weakTop],
      additional_options: [...fillerReserves(5), strongReserve],
    })
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
    })
    api.postRecommend.mockResolvedValueOnce(response)
    render(<App />)
    await addRecognizedIngredientAndSubmit()
    await waitFor(() => screen.getByText('Chicken Fried Rice'))

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

  it('shows a non-anchor fallback card only in the separate "Other options" section, never inside recommendations (fifth correction pass)', async () => {
    // Product decision (fifth correction pass, PR #15): recommendations
    // is never padded with a non-anchor candidate. A non-anchor
    // candidate now surfaces only via closest_alternatives, rendered as
    // a structurally separate "Other options" section below the real
    // recommendations, still carrying the "Alternative pick" badge.
    const response = baseResponse({
      recommendations: [card({ recipe_id: 'anchor-1', contains_active_anchor: true })],
      additional_options: [],
      closest_alternatives: [card({ recipe_id: 'fallback-1', name: 'Fallback Dish', contains_active_anchor: false })],
    })
    api.postRecommend.mockResolvedValue(response)
    render(<App />)
    await addRecognizedIngredientAndSubmit()
    await waitFor(() => screen.getByText('Fallback Dish'))

    expect(screen.getByText('Other options')).toBeInTheDocument()
    expect(screen.getByText('Chicken Fried Rice')).toBeInTheDocument() // the real recommendation, still shown
    expect(screen.getAllByText('Alternative pick')).toHaveLength(1)
    const fallbackCardEl = screen.getByText('Fallback Dish').closest('button')
    expect(fallbackCardEl).toContainElement(screen.getByText('Alternative pick'))
  })

  it('never mixes a non-anchor closest_alternatives card into the recommendations grid', async () => {
    const response = baseResponse({
      recommendations: [card({ recipe_id: 'anchor-1', contains_active_anchor: true })],
      additional_options: [],
      closest_alternatives: [card({ recipe_id: 'fallback-1', name: 'Fallback Dish', contains_active_anchor: false })],
    })
    api.postRecommend.mockResolvedValue(response)
    render(<App />)
    await addRecognizedIngredientAndSubmit()
    await waitFor(() => screen.getByText('Fallback Dish'))

    const fallbackCard = screen.getByText('Fallback Dish').closest('button')
    const recommendationCard = screen.getByText('Chicken Fried Rice').closest('button')
    // Different grid containers -- not the same recipe-grid section.
    expect(fallbackCard.closest('.recipe-grid')).not.toBe(recommendationCard.closest('.recipe-grid'))
  })

  it('additional_options from a real response never contains a non-anchor card (Blocker 3)', async () => {
    // The backend guarantees this, but this test locks in that the
    // frontend simply displays what it is given -- an additional_option
    // marked contains_active_anchor: true never shows the badge. With
    // only 1 recommendation + 1 reserve candidate (2 total), the
    // initial reveal (up to 6) already shows both -- no click needed.
    const response = baseResponse({
      recommendations: [card({ recipe_id: 'anchor-1', contains_active_anchor: true })],
      additional_options: [card({ recipe_id: 'anchor-2', name: 'Reserve Anchor Dish', contains_active_anchor: true })],
    })
    api.postRecommend.mockResolvedValue(response)
    render(<App />)
    await addRecognizedIngredientAndSubmit()
    await waitFor(() => screen.getByText('Chicken Fried Rice'))

    expect(screen.getByText('Reserve Anchor Dish')).toBeInTheDocument()
    expect(screen.queryByText('Alternative pick')).not.toBeInTheDocument()
  })

  it('hides "Show more options" once same-anchor reserve candidates are exhausted, without padding with unrelated recipes', async () => {
    const response = baseResponse({
      recommendations: [card({ recipe_id: 'anchor-1', contains_active_anchor: true })],
      additional_options: [], // anchor pool already exhausted after top 3 -- nothing to reveal
    })
    api.postRecommend.mockResolvedValue(response)
    render(<App />)
    await addRecognizedIngredientAndSubmit()
    await waitFor(() => screen.getByText('Chicken Fried Rice'))

    expect(screen.queryByRole('button', { name: 'Show more options' })).not.toBeInTheDocument()
  })
})

describe('Module F: local persistence (pantry, preferences, history, saved recipes)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
  })

  it('restores a recognized pantry ingredient after a reload, without duplicating it', async () => {
    api.postRecommend.mockResolvedValue(baseResponse({ recommendations: [card()] }))
    const { unmount } = render(<App />)
    await addRecognizedIngredientAndSubmit()
    unmount()

    render(<App />)
    expect(screen.getAllByText('Rice')).toHaveLength(1)
  })

  it('restores servings and cuisine preferences after a reload, but never budget', async () => {
    api.postRecommend.mockResolvedValue(baseResponse({ recommendations: [card()] }))
    const { unmount } = render(<App />)
    await userEvent.click(screen.getByRole('button', { name: 'Increase servings' }))
    await userEvent.selectOptions(screen.getByLabelText('Cuisine'), 'Italian')
    await userEvent.click(screen.getByRole('button', { name: 'More options ▼' }))
    await userEvent.type(screen.getByLabelText('Additional grocery budget (AED)'), '150')
    await addRecognizedIngredientAndSubmit()
    unmount()

    const { container } = render(<App />)
    expect(container.querySelector('.servings-stepper__value')).toHaveTextContent('5')
    expect(screen.getByLabelText('Cuisine')).toHaveValue('Italian')
    await userEvent.click(screen.getByRole('button', { name: 'More options ▼' }))
    expect(screen.getByLabelText('Additional grocery budget (AED)')).toHaveValue(null)
  })

  it('lists a completed search under "Your data" and reruns it on demand', async () => {
    api.postRecommend.mockResolvedValue(baseResponse({ recommendations: [card()] }))
    render(<App />)
    await addRecognizedIngredientAndSubmit()
    await waitFor(() => screen.getByText('Chicken Fried Rice'))

    await userEvent.click(screen.getByRole('button', { name: /Your data/ }))
    expect(
      screen.getByText((content, el) => el?.className === 'local-data-panel__row-title' && content === 'Rice'),
    ).toBeInTheDocument()

    api.postRecommend.mockClear()
    api.postRecommend.mockResolvedValueOnce(baseResponse({ recommendations: [card()] }))
    await userEvent.click(screen.getByRole('button', { name: 'Search again' }))

    await waitFor(() => expect(api.postRecommend).toHaveBeenCalledTimes(1))
    expect(api.postRecommend.mock.calls[0][0].ingredients).toEqual(['Rice'])
  })

  it('clears search history from "Your data"', async () => {
    api.postRecommend.mockResolvedValue(baseResponse({ recommendations: [card()] }))
    render(<App />)
    await addRecognizedIngredientAndSubmit()
    await waitFor(() => screen.getByText('Chicken Fried Rice'))

    await userEvent.click(screen.getByRole('button', { name: /Your data/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Clear history' }))

    expect(screen.getByText('No recent searches yet.')).toBeInTheDocument()
  })

  it('saves a recipe from the detail view, shows it as saved on the card and in "Your data", and can remove it', async () => {
    api.postRecommend.mockResolvedValue(
      baseResponse({ recommendations: [card({ source_url: 'https://example.test/recipe/1' })] }),
    )
    render(<App />)
    await addRecognizedIngredientAndSubmit()
    await waitFor(() => screen.getByText('Chicken Fried Rice'))

    await userEvent.click(screen.getByRole('button', { name: /Chicken Fried Rice/ }))
    await userEvent.click(screen.getByRole('button', { name: '☆ Save recipe' }))
    expect(screen.getByRole('button', { name: '★ Saved' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Back to results' }))
    expect(screen.getByLabelText('Saved to your recipes')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Your data/ }))
    expect(
      screen.getByText((content, el) => el?.className === 'local-data-panel__row-title' && content === 'Chicken Fried Rice'),
    ).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Remove' }))
    expect(screen.getByText('No saved recipes yet.')).toBeInTheDocument()
  })

  it('"Clear all local data" resets the pantry and closes out persisted state', async () => {
    api.postRecommend.mockResolvedValue(baseResponse({ recommendations: [card()] }))
    render(<App />)
    await addRecognizedIngredientAndSubmit()
    await waitFor(() => screen.getByText('Chicken Fried Rice'))

    await userEvent.click(screen.getByRole('button', { name: /Your data/ }))
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    await userEvent.click(screen.getByRole('button', { name: 'Clear all local data' }))
    await userEvent.click(screen.getByRole('button', { name: 'Close' }))

    expect(screen.queryByText('Rice')).not.toBeInTheDocument()
  })
})

describe('Module F: production UX -- offline and rate-limit states', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows a friendly, retryable message when the backend is unreachable', async () => {
    const { ApiError } = api
    api.postRecommend.mockRejectedValue(
      new ApiError("Can't reach PantryPilot right now. Check your connection and try again.", {
        code: 'NETWORK_ERROR',
        retryable: true,
      }),
    )
    render(<App />)
    await addRecognizedIngredientAndSubmit()

    await waitFor(() =>
      expect(screen.getByText("Can't reach PantryPilot right now. Check your connection and try again.")).toBeInTheDocument(),
    )
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('shows a friendly, non-technical message on a rate-limit response, never the word "rate limit" exposed as an internal code', async () => {
    const { ApiError } = api
    api.postRecommend.mockRejectedValue(
      new ApiError("You're searching a bit fast. Please wait a moment and try again.", {
        code: 'RATE_LIMITED',
        retryable: true,
      }),
    )
    render(<App />)
    await addRecognizedIngredientAndSubmit()

    await waitFor(() =>
      expect(screen.getByText("You're searching a bit fast. Please wait a moment and try again.")).toBeInTheDocument(),
    )
  })

  // 2026-09-13 hotfix: autocomplete suggestions must never replace what
  // the user actually typed. "chicken" has several cut-specific
  // suggestions (Chicken Breast, Chicken Broth, ...) but pressing Enter
  // without explicitly navigating/clicking one must commit "chicken"
  // itself, unchanged, all the way to the request payload.
  describe('free-text ingredient survives autocomplete suggestions (TEST 8/9)', () => {
    it('sends raw "chicken" in the request payload, never a narrower suggestion', async () => {
      api.fetchIngredientSuggestions.mockResolvedValue([
        { canonical_id: 'chicken_breast', display_name: 'Chicken Breast' },
        { canonical_id: 'chicken_broth', display_name: 'Chicken Broth' },
      ])
      api.postRecommend.mockResolvedValue(baseResponse({ recommendations: [card()] }))
      render(<App />)

      const input = screen.getByRole('combobox', { name: /What ingredients do you have/ })
      await userEvent.type(input, 'chicken')
      await waitFor(() => screen.getByText('Chicken Breast'))
      await userEvent.keyboard('{Enter}')
      await userEvent.click(screen.getByRole('button', { name: 'Find meals' }))

      await waitFor(() => expect(api.postRecommend).toHaveBeenCalledTimes(1))
      expect(api.postRecommend.mock.calls[0][0].ingredients).toEqual(['chicken'])
    })
  })
})
