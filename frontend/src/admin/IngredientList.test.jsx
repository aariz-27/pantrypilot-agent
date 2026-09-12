import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { IngredientList } from './IngredientList.jsx'
import { ApiError } from '../services/api.js'
import * as adminApi from '../services/adminApi.js'

vi.mock('../services/adminApi.js', () => ({
  listIngredients: vi.fn(),
  createIngredient: vi.fn(),
}))

const SAMPLE_ITEM = {
  canonical_id: 'bell_pepper',
  display_name: 'Bell Pepper',
  default_unit: 'g',
  status: 'active',
  created_at: '2026-09-01T00:00:00Z',
  updated_at: '2026-09-01T00:00:00Z',
  updated_by: 'founder',
  alias_count: 2,
  has_manual_price: false,
  has_reference_price: true,
}

describe('IngredientList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    adminApi.listIngredients.mockResolvedValue({ items: [SAMPLE_ITEM], total: 1, page: 1, page_size: 25 })
  })

  it('renders ingredients returned by the API', async () => {
    render(<IngredientList onOpenIngredient={vi.fn()} />)
    expect(await screen.findByText('Bell Pepper')).toBeInTheDocument()
    expect(screen.getByText('bell_pepper')).toBeInTheDocument()
  })

  it('searches by typing into the search field (debounced)', async () => {
    const user = userEvent.setup()
    render(<IngredientList onOpenIngredient={vi.fn()} />)
    await screen.findByText('Bell Pepper')

    await user.type(screen.getByLabelText('Search ingredients'), 'capsicum')

    await waitFor(() => {
      const lastCall = adminApi.listIngredients.mock.calls.at(-1)[0]
      expect(lastCall.q).toBe('capsicum')
    })
  })

  it('opens an ingredient when Manage is clicked', async () => {
    const onOpenIngredient = vi.fn()
    const user = userEvent.setup()
    render(<IngredientList onOpenIngredient={onOpenIngredient} />)
    await screen.findByText('Bell Pepper')

    await user.click(screen.getByRole('button', { name: 'Manage' }))
    expect(onOpenIngredient).toHaveBeenCalledWith('bell_pepper')
  })

  it('shows the create-ingredient form and submits a new ingredient', async () => {
    const user = userEvent.setup()
    adminApi.createIngredient.mockResolvedValue({ ...SAMPLE_ITEM, canonical_id: 'onion', display_name: 'Onion' })
    render(<IngredientList onOpenIngredient={vi.fn()} />)
    await screen.findByText('Bell Pepper')

    await user.click(screen.getByRole('button', { name: 'Add ingredient' }))
    await user.type(screen.getByLabelText('Canonical ID'), 'onion')
    await user.type(screen.getByLabelText('Display name'), 'Onion')
    await user.click(screen.getByRole('button', { name: 'Create ingredient' }))

    await waitFor(() =>
      expect(adminApi.createIngredient).toHaveBeenCalledWith({ canonical_id: 'onion', display_name: 'Onion', default_unit: null })
    )
  })

  it('shows a validation error when create-ingredient fails (e.g. duplicate)', async () => {
    const user = userEvent.setup()
    adminApi.createIngredient.mockRejectedValue(
      new ApiError("canonical ingredient 'onion' already exists", { code: 'ADMIN_CONFLICT', status: 409 })
    )
    render(<IngredientList onOpenIngredient={vi.fn()} />)
    await screen.findByText('Bell Pepper')

    await user.click(screen.getByRole('button', { name: 'Add ingredient' }))
    await user.type(screen.getByLabelText('Canonical ID'), 'onion')
    await user.type(screen.getByLabelText('Display name'), 'Onion')
    await user.click(screen.getByRole('button', { name: 'Create ingredient' }))

    expect(await screen.findByText("canonical ingredient 'onion' already exists")).toBeInTheDocument()
  })

  it('renders correctly with an empty result set', async () => {
    adminApi.listIngredients.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 })
    render(<IngredientList onOpenIngredient={vi.fn()} />)
    expect(await screen.findByText('No ingredients found.')).toBeInTheDocument()
  })

  it('price-focus mode only shows ingredients without a known price', async () => {
    adminApi.listIngredients.mockResolvedValue({
      items: [
        SAMPLE_ITEM,
        { ...SAMPLE_ITEM, canonical_id: 'obscure_spice', display_name: 'Obscure Spice', has_reference_price: false, has_manual_price: false },
      ],
      total: 2,
      page: 1,
      page_size: 25,
    })
    render(<IngredientList onOpenIngredient={vi.fn()} priceFocusMode />)
    expect(await screen.findByText('Obscure Spice')).toBeInTheDocument()
    expect(screen.queryByText('Bell Pepper')).not.toBeInTheDocument()
  })
})
