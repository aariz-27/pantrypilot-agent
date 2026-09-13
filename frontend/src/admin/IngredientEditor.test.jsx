import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { IngredientEditor } from './IngredientEditor.jsx'
import { ApiError } from '../services/api.js'
import * as adminApi from '../services/adminApi.js'

vi.mock('../services/adminApi.js', () => ({
  getIngredient: vi.fn(),
  updateIngredient: vi.fn(),
  listAliases: vi.fn(),
  createAlias: vi.fn(),
  deactivateAlias: vi.fn(),
  reassignAlias: vi.fn(),
  getIngredientPrices: vi.fn(),
  createManualPrice: vi.fn(),
  updateManualPrice: vi.fn(),
  deactivateManualPrice: vi.fn(),
}))

const INGREDIENT = {
  canonical_id: 'bell_pepper',
  display_name: 'Bell Pepper',
  default_unit: 'g',
  status: 'active',
  created_at: '2026-09-01T00:00:00Z',
  updated_at: '2026-09-01T00:00:00Z',
  updated_by: 'founder',
  alias_count: 1,
  has_manual_price: false,
  has_reference_price: false,
}

beforeEach(() => {
  vi.clearAllMocks()
  adminApi.getIngredient.mockResolvedValue(INGREDIENT)
  adminApi.listAliases.mockResolvedValue([{ alias: 'capsicum', canonical_id: 'bell_pepper', source: 'manual', confidence: 1, active: true }])
  adminApi.getIngredientPrices.mockResolvedValue({ reference_prices: [], manual_prices: [] })
})

describe('IngredientEditor', () => {
  it('renders overview, aliases, and pricing sections', async () => {
    render(<IngredientEditor canonicalId="bell_pepper" onClose={vi.fn()} />)
    expect(await screen.findByRole('heading', { name: 'Overview' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Aliases' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Pricing' })).toBeInTheDocument()
    expect(await screen.findByText('capsicum')).toBeInTheDocument()
  })

  it('saves overview changes', async () => {
    const user = userEvent.setup()
    adminApi.updateIngredient.mockResolvedValue({ ...INGREDIENT, display_name: 'Bell Peppers' })
    render(<IngredientEditor canonicalId="bell_pepper" onClose={vi.fn()} />)
    await screen.findByRole('heading', { name: 'Overview' })

    const nameInput = screen.getByLabelText('Display name')
    await user.clear(nameInput)
    await user.type(nameInput, 'Bell Peppers')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    await waitFor(() =>
      expect(adminApi.updateIngredient).toHaveBeenCalledWith('bell_pepper', {
        display_name: 'Bell Peppers',
        default_unit: 'g',
        status: 'active',
      })
    )
    expect(await screen.findByText('Saved.')).toBeInTheDocument()
  })

  it('adds a new alias', async () => {
    const user = userEvent.setup()
    adminApi.createAlias.mockResolvedValue({ alias: 'sweet pepper', canonical_id: 'bell_pepper', source: 'manual', confidence: 1, active: true })
    render(<IngredientEditor canonicalId="bell_pepper" onClose={vi.fn()} />)
    await screen.findByText('capsicum')

    await user.type(screen.getByPlaceholderText('Add an alias, e.g. capsicum'), 'sweet pepper')
    await user.click(screen.getByRole('button', { name: 'Add alias' }))

    await waitFor(() => expect(adminApi.createAlias).toHaveBeenCalledWith('bell_pepper', 'sweet pepper'))
  })

  it('shows a conflict error when adding a conflicting alias', async () => {
    const user = userEvent.setup()
    adminApi.createAlias.mockRejectedValue(
      new ApiError("alias 'pepper' is already mapped to a different canonical ingredient ('chili')", {
        code: 'ADMIN_CONFLICT',
        status: 409,
      })
    )
    render(<IngredientEditor canonicalId="bell_pepper" onClose={vi.fn()} />)
    await screen.findByText('capsicum')

    await user.type(screen.getByPlaceholderText('Add an alias, e.g. capsicum'), 'pepper')
    await user.click(screen.getByRole('button', { name: 'Add alias' }))

    expect(await screen.findByText(/already mapped to a different canonical ingredient/)).toBeInTheDocument()
  })

  it('requires confirmation before deactivating an alias', async () => {
    const user = userEvent.setup()
    adminApi.deactivateAlias.mockResolvedValue({ alias: 'capsicum', canonical_id: 'bell_pepper', source: 'manual', confidence: 1, active: false })
    render(<IngredientEditor canonicalId="bell_pepper" onClose={vi.fn()} />)
    await screen.findByText('capsicum')

    await user.click(screen.getByRole('button', { name: 'Remove alias capsicum' }))
    expect(screen.getByRole('alertdialog')).toBeInTheDocument()
    expect(adminApi.deactivateAlias).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Remove alias' }))
    await waitFor(() => expect(adminApi.deactivateAlias).toHaveBeenCalledWith('capsicum'))
  })

  it('cancelling the confirm dialog does not deactivate', async () => {
    const user = userEvent.setup()
    render(<IngredientEditor canonicalId="bell_pepper" onClose={vi.fn()} />)
    await screen.findByText('capsicum')

    await user.click(screen.getByRole('button', { name: 'Remove alias capsicum' }))
    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(adminApi.deactivateAlias).not.toHaveBeenCalled()
  })

  it('shows a validation error when adding an invalid manual price', async () => {
    const user = userEvent.setup()
    adminApi.createManualPrice.mockRejectedValue(
      new ApiError('normalized_price_per_unit must be greater than zero', { code: 'ADMIN_VALIDATION_ERROR', status: 422 })
    )
    render(<IngredientEditor canonicalId="bell_pepper" onClose={vi.fn()} />)
    await screen.findByRole('heading', { name: 'Pricing' })

    await user.click(screen.getByRole('button', { name: 'Add manual price' }))
    const formElement = screen.getByRole('button', { name: 'Save manual price' }).closest('form')
    const priceForm = within(formElement)
    await user.type(priceForm.getByLabelText('Display name'), 'Bell Pepper')
    await user.type(priceForm.getByLabelText('Price per unit (AED)'), '-1')
    await user.type(priceForm.getByLabelText('Provenance note'), 'test entry')
    // A native `min="0.0001"` constraint (good real UX) blocks a
    // browser-driven click submit of a negative value before our JS
    // handler ever runs -- fireEvent.submit bypasses that native
    // constraint check to prove the SERVER-SIDE rejection path
    // (ADMIN_VALIDATION_ERROR) is independently wired up and rendered,
    // the same defense-in-depth the backend's own NaN/Infinity tests
    // prove for a non-browser client.
    fireEvent.submit(formElement)

    expect(await screen.findByText('normalized_price_per_unit must be greater than zero')).toBeInTheDocument()
  })

  it('never reports an unknown price as zero', async () => {
    render(<IngredientEditor canonicalId="bell_pepper" onClose={vi.fn()} />)
    expect(await screen.findByText(/never reported as zero/)).toBeInTheDocument()
  })

  it('calls onClose when the back button is clicked', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<IngredientEditor canonicalId="bell_pepper" onClose={onClose} />)
    await screen.findByRole('heading', { name: 'Overview' })
    await user.click(screen.getByRole('button', { name: 'Back to ingredient list' }))
    expect(onClose).toHaveBeenCalled()
  })

  describe('built-in ingredient (2026-09-13 admin completion ticket)', () => {
    it('shows a read-only overview and full pricing, without fetching an admin-only row or aliases', async () => {
      render(<IngredientEditor canonicalId="chicken_breast" source="built_in" onClose={vi.fn()} />)

      expect(await screen.findByRole('heading', { name: 'Overview' })).toBeInTheDocument()
      expect(screen.getByRole('heading', { name: 'Pricing' })).toBeInTheDocument()
      expect(screen.queryByRole('heading', { name: 'Aliases' })).not.toBeInTheDocument()
      expect(screen.getByDisplayValue('Chicken Breast')).toBeInTheDocument()
      expect(screen.getByDisplayValue('Chicken Breast')).toBeDisabled()
      // A built-in ingredient is not a database row -- these calls
      // would 404/be meaningless for it, so they are never made.
      expect(adminApi.getIngredient).not.toHaveBeenCalled()
      expect(adminApi.listAliases).not.toHaveBeenCalled()
      // Pricing is unconditionally reused, unchanged, for any canonical
      // id regardless of source.
      expect(adminApi.getIngredientPrices).toHaveBeenCalledWith('chicken_breast')
    })

    it('can still add a manual price for a built-in ingredient', async () => {
      const user = userEvent.setup()
      adminApi.createManualPrice.mockResolvedValue({
        canonical_id: 'chicken_breast', normalized_unit: 'g', display_name: 'Chicken Breast',
        normalized_price_per_unit: 0.05, provenance_note: 'test', active: true,
      })
      render(<IngredientEditor canonicalId="chicken_breast" source="built_in" onClose={vi.fn()} />)
      await screen.findByRole('heading', { name: 'Pricing' })

      await user.click(screen.getByRole('button', { name: 'Add manual price' }))
      const formElement = screen.getByRole('button', { name: 'Save manual price' }).closest('form')
      const priceForm = within(formElement)
      await user.type(priceForm.getByLabelText('Display name'), 'Chicken Breast')
      await user.type(priceForm.getByLabelText('Price per unit (AED)'), '0.05')
      await user.type(priceForm.getByLabelText('Provenance note'), 'test entry')
      await user.click(screen.getByRole('button', { name: 'Save manual price' }))

      await waitFor(() =>
        expect(adminApi.createManualPrice).toHaveBeenCalledWith(
          'chicken_breast',
          expect.objectContaining({ normalized_price_per_unit: 0.05 })
        )
      )
    })
  })
})
