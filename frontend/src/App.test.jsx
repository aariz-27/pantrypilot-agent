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
})
